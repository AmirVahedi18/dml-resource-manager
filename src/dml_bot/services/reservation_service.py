from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.regulation import Regulation
from dml_bot.db.models.reservation import Reservation, ReservationStatus
from dml_bot.db.models.user import User
from dml_bot.utils.time_utils import is_slot_aligned, to_naive_utc, utc_now


class ReservationError(Exception):
    pass


class SlotAlignmentError(ReservationError):
    pass


class DurationExceededError(ReservationError):
    pass


class OutsideBookingHorizonError(ReservationError):
    pass


class RamLimitExceededError(ReservationError):
    pass


class CapacityExceededError(ReservationError):
    pass


class ConcurrentGpuConflictError(ReservationError):
    pass


class ActiveReservationLimitError(ReservationError):
    pass


def get_overlapping_active_reservations(
    session: Session, gpu_id: int, start_time: datetime, end_time: datetime
) -> list[Reservation]:
    start_time, end_time = to_naive_utc(start_time), to_naive_utc(end_time)
    stmt = select(Reservation).where(
        Reservation.gpu_id == gpu_id,
        Reservation.status == ReservationStatus.ACTIVE,
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    return list(session.execute(stmt).scalars().all())


def _peak_concurrent_ram(
    reservations: list[Reservation], window_start: datetime, window_end: datetime
) -> int:
    """Max RAM (mb) held simultaneously by `reservations`, clipped to [window_start, window_end)."""
    events: list[tuple[datetime, int]] = []
    for r in reservations:
        clipped_start = max(r.start_time, window_start)
        clipped_end = min(r.end_time, window_end)
        if clipped_start >= clipped_end:
            continue  # touches the window boundary but doesn't actually overlap it
        events.append((clipped_start, r.ram_mb))
        events.append((clipped_end, -r.ram_mb))
    events.sort(key=lambda e: e[0])

    current = 0
    peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def min_free_ram_in_range(session: Session, gpu: GPU, start_time: datetime, end_time: datetime) -> int:
    start_time, end_time = to_naive_utc(start_time), to_naive_utc(end_time)
    overlapping = get_overlapping_active_reservations(session, gpu.id, start_time, end_time)
    peak = _peak_concurrent_ram(overlapping, start_time, end_time)
    return gpu.total_ram_mb - peak


def slot_availability(
    session: Session, gpu: GPU, range_start: datetime, range_end: datetime, slot_minutes: int
) -> list[tuple[datetime, int]]:
    """Free RAM (mb) for each slot_minutes-sized slot in [range_start, range_end).

    The max of per-slot peaks equals the true peak over the whole range (the instant of peak
    concurrency falls inside exactly one slot), so `min(free for slot in slots)` is exactly the
    largest ram_mb a single reservation spanning the whole range could request -- this is what
    the grid picker uses to cap the RAM a student can select for a dragged range.
    """
    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    overlapping = get_overlapping_active_reservations(session, gpu.id, range_start, range_end)

    slots = []
    slot_start = range_start
    while slot_start < range_end:
        slot_end = slot_start + timedelta(minutes=slot_minutes)
        peak = _peak_concurrent_ram(overlapping, slot_start, slot_end)
        slots.append((slot_start, gpu.total_ram_mb - peak))
        slot_start = slot_end
    return slots


def count_active_reservations(session: Session, user_id: int, now: datetime | None = None) -> int:
    now = to_naive_utc(now) if now else utc_now()
    stmt = select(Reservation).where(
        Reservation.user_id == user_id,
        Reservation.status == ReservationStatus.ACTIVE,
        Reservation.end_time > now,
    )
    return len(list(session.execute(stmt).scalars().all()))


def create_reservation(
    session: Session,
    user: User,
    gpu: GPU,
    start_time: datetime,
    end_time: datetime,
    ram_mb: int,
    regulation: Regulation,
    now: datetime | None = None,
) -> Reservation:
    now = to_naive_utc(now) if now else utc_now()
    start_time, end_time = to_naive_utc(start_time), to_naive_utc(end_time)

    if end_time <= start_time:
        raise ReservationError("end_time must be after start_time")

    slot_minutes = regulation.min_reservation_slot_minutes
    if not (is_slot_aligned(start_time, slot_minutes) and is_slot_aligned(end_time, slot_minutes)):
        raise SlotAlignmentError(f"start/end must align to {slot_minutes}-minute slots")

    duration_hours = (end_time - start_time).total_seconds() / 3600
    if duration_hours > regulation.max_duration_hours:
        raise DurationExceededError(f"duration exceeds {regulation.max_duration_hours}h limit")

    horizon_end = now + timedelta(days=regulation.booking_horizon_days)
    if start_time < now or start_time > horizon_end:
        raise OutsideBookingHorizonError(f"start_time must be within [{now}, {horizon_end}]")

    if ram_mb <= 0 or ram_mb > regulation.max_ram_per_reservation_mb or ram_mb > gpu.total_ram_mb:
        raise RamLimitExceededError(
            f"ram_mb must be in (0, {min(regulation.max_ram_per_reservation_mb, gpu.total_ram_mb)}]"
        )

    if count_active_reservations(session, user.id, now) >= regulation.max_active_reservations_per_user:
        raise ActiveReservationLimitError(
            f"user already has {regulation.max_active_reservations_per_user} active reservations"
        )

    overlapping_same_gpu = get_overlapping_active_reservations(session, gpu.id, start_time, end_time)
    peak = _peak_concurrent_ram(overlapping_same_gpu, start_time, end_time)
    if peak + ram_mb > gpu.total_ram_mb:
        raise CapacityExceededError(
            f"only {gpu.total_ram_mb - peak}mb free on this GPU for the requested window"
        )

    if not user.can_use_multiple_gpus:
        stmt = select(Reservation).where(
            Reservation.user_id == user.id,
            Reservation.gpu_id != gpu.id,
            Reservation.status == ReservationStatus.ACTIVE,
            Reservation.start_time < end_time,
            Reservation.end_time > start_time,
        )
        if session.execute(stmt).scalars().first() is not None:
            raise ConcurrentGpuConflictError(
                "user already holds a reservation on another GPU during this window"
            )

    reservation = Reservation(
        user_id=user.id,
        gpu_id=gpu.id,
        start_time=start_time,
        end_time=end_time,
        ram_mb=ram_mb,
        status=ReservationStatus.ACTIVE,
    )
    session.add(reservation)
    session.flush()
    return reservation


def cancel_reservation(session: Session, reservation: Reservation, now: datetime | None = None) -> Reservation:
    if reservation.status != ReservationStatus.ACTIVE:
        raise ReservationError("reservation is not active")
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = to_naive_utc(now) if now else utc_now()
    session.flush()
    return reservation


def list_active_reservations_for_user(
    session: Session, user_id: int, upcoming_only: bool = True, now: datetime | None = None
) -> list[Reservation]:
    now = to_naive_utc(now) if now else utc_now()
    stmt = select(Reservation).where(
        Reservation.user_id == user_id, Reservation.status == ReservationStatus.ACTIVE
    )
    if upcoming_only:
        stmt = stmt.where(Reservation.end_time > now)
    return list(session.execute(stmt).scalars().all())


def list_reservations_for_gpu(
    session: Session, gpu_id: int, range_start: datetime, range_end: datetime
) -> list[Reservation]:
    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    stmt = select(Reservation).where(
        Reservation.gpu_id == gpu_id,
        Reservation.status == ReservationStatus.ACTIVE,
        Reservation.start_time < range_end,
        Reservation.end_time > range_start,
    )
    return list(session.execute(stmt).scalars().all())
