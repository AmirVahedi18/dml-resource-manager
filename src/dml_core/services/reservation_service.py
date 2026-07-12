from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from dml_core.db.models.gpu import GPU
from dml_core.db.models.regulation import Regulation, SINGLETON_ID
from dml_core.db.models.reservation import Reservation, ReservationStatus
from dml_core.db.models.user import User
from dml_core.utils.time_utils import is_slot_aligned, to_naive_utc, utc_now

# Fallback used when the singleton Regulation row is missing/unseeded, or predates the
# reactivation_delay_minutes column (NULL on DBs migrated by _add_missing_columns). Equals the
# value that offset was hard-coded to before it became configurable.
DEFAULT_REACTIVATION_DELAY_MINUTES = 60


def reactivation_delay_minutes(session: Session) -> int:
    """The configured minutes a resumed reservation is pushed out from the reactivation moment,
    read defensively so callers never crash on an unseeded/legacy Regulation row."""
    regulation = session.get(Regulation, SINGLETON_ID)
    if regulation is None or regulation.reactivation_delay_minutes is None:
        return DEFAULT_REACTIVATION_DELAY_MINUTES
    return regulation.reactivation_delay_minutes


class ReservationError(Exception):
    pass


class GpuInactiveError(ReservationError):
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
    """Counts ACTIVE and SUSPENDED reservations -- a suspended one still occupies the student's
    reservation-limit slot, since it will resume rather than disappear."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = select(Reservation).where(
        Reservation.user_id == user_id,
        Reservation.status.in_([ReservationStatus.ACTIVE, ReservationStatus.SUSPENDED]),
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
    description: str = "",
) -> Reservation:
    now = to_naive_utc(now) if now else utc_now()
    start_time, end_time = to_naive_utc(start_time), to_naive_utc(end_time)

    if end_time <= start_time:
        raise ReservationError("The end time must be after the start time.")

    if not gpu.is_active or not gpu.server.is_active:
        raise GpuInactiveError("This GPU is not currently available for booking.")

    slot_minutes = regulation.min_reservation_slot_minutes
    if not (is_slot_aligned(start_time, slot_minutes) and is_slot_aligned(end_time, slot_minutes)):
        raise SlotAlignmentError(f"Start and end times must align to the {slot_minutes}-minute booking schedule.")

    duration_hours = (end_time - start_time).total_seconds() / 3600
    if duration_hours > regulation.max_duration_hours:
        raise DurationExceededError(f"Reservations can't be longer than {regulation.max_duration_hours} hours.")

    horizon_end = now + timedelta(days=regulation.booking_horizon_days)
    if start_time < now:
        raise OutsideBookingHorizonError("Reservations can't start in the past.")
    if start_time > horizon_end:
        raise OutsideBookingHorizonError(
            f"Reservations can only be booked up to {regulation.booking_horizon_days} days in advance."
        )

    max_ram_per_reservation_mb = regulation.max_ram_per_reservation_gb * 1024
    if ram_mb <= 0 or ram_mb > max_ram_per_reservation_mb or ram_mb > gpu.total_ram_mb:
        raise RamLimitExceededError(
            f"RAM must be more than 0 and at most {min(max_ram_per_reservation_mb, gpu.total_ram_mb)} MB."
        )

    if count_active_reservations(session, user.id, now) >= regulation.max_active_reservations_per_user:
        raise ActiveReservationLimitError(
            f"You already have the maximum of {regulation.max_active_reservations_per_user} active "
            "reservations allowed."
        )

    overlapping_same_gpu = get_overlapping_active_reservations(session, gpu.id, start_time, end_time)
    peak = _peak_concurrent_ram(overlapping_same_gpu, start_time, end_time)
    if peak + ram_mb > gpu.total_ram_mb:
        raise CapacityExceededError(
            f"Only {gpu.total_ram_mb - peak} MB is free on this GPU during the requested time window."
        )

    stmt = select(Reservation.gpu_id).distinct().where(
        Reservation.user_id == user.id,
        Reservation.status.in_([ReservationStatus.ACTIVE, ReservationStatus.SUSPENDED]),
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    concurrent_gpu_ids = set(session.execute(stmt).scalars().all())
    if gpu.id not in concurrent_gpu_ids and len(concurrent_gpu_ids) >= user.max_concurrent_gpus:
        raise ConcurrentGpuConflictError(
            f"You can only hold reservations on {user.max_concurrent_gpus} GPU(s) at a time, and you "
            f"already have {len(concurrent_gpu_ids)}."
        )

    reservation = Reservation(
        user_id=user.id,
        gpu_id=gpu.id,
        start_time=start_time,
        end_time=end_time,
        ram_mb=ram_mb,
        description=description,
        status=ReservationStatus.ACTIVE,
    )
    session.add(reservation)
    session.flush()
    return reservation


def cancel_reservation(session: Session, reservation: Reservation, now: datetime | None = None) -> Reservation:
    if reservation.status == ReservationStatus.CANCELLED:
        raise ReservationError("This reservation has already been cancelled.")
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = to_naive_utc(now) if now else utc_now()
    session.flush()
    return reservation


def cancel_reservations(
    session: Session, reservations: list[Reservation], now: datetime | None = None
) -> int:
    """Bulk-cancels every reservation in `reservations` (each must already be ACTIVE). Used for the
    admin's "cancel all for this user" / "cancel all lab-wide" actions."""
    now = to_naive_utc(now) if now else utc_now()
    for reservation in reservations:
        cancel_reservation(session, reservation, now=now)
    return len(reservations)


_LIVE_STATUSES = [ReservationStatus.ACTIVE, ReservationStatus.SUSPENDED]


def list_active_reservations_for_user(
    session: Session, user_id: int, upcoming_only: bool = True, now: datetime | None = None
) -> list[Reservation]:
    """Includes SUSPENDED reservations alongside ACTIVE ones -- a suspended reservation is still
    "held" by the student (it'll resume once its GPU/server is reactivated), so it belongs
    wherever a student's live reservations are listed or bulk-cancelled."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = select(Reservation).where(
        Reservation.user_id == user_id, Reservation.status.in_(_LIVE_STATUSES)
    )
    if upcoming_only:
        stmt = stmt.where(Reservation.end_time > now)
    return list(session.execute(stmt).scalars().all())


def cancel_all_for_gpu(session: Session, gpu_id: int, now: datetime | None = None) -> int:
    """Cancels (never deletes) every still-live (ACTIVE or SUSPENDED) reservation on `gpu_id`.
    Used when a GPU/server is removed from the fleet, so reservation history for it survives the
    removal."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = select(Reservation).where(Reservation.gpu_id == gpu_id, Reservation.status.in_(_LIVE_STATUSES))
    reservations = list(session.execute(stmt).scalars().all())
    return cancel_reservations(session, reservations, now=now)


def cancel_all_for_user_on_server(
    session: Session, user_id: int, server_id: int, now: datetime | None = None
) -> int:
    """Cancels (never deletes) every still-live (ACTIVE or SUSPENDED) reservation `user_id` holds
    on `server_id`'s GPUs. Used when an admin revokes a user's access to a server -- they can no
    longer use it, so their outstanding reservations there no longer make sense."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = (
        select(Reservation)
        .join(GPU, Reservation.gpu_id == GPU.id)
        .where(
            Reservation.user_id == user_id,
            Reservation.status.in_(_LIVE_STATUSES),
            GPU.server_id == server_id,
        )
    )
    reservations = list(session.execute(stmt).scalars().all())
    return cancel_reservations(session, reservations, now=now)


def suspend_active_reservations_for_gpu(session: Session, gpu_id: int, now: datetime | None = None) -> int:
    """Pauses (never cancels) every still-upcoming ACTIVE reservation on `gpu_id`, marking it
    SUSPENDED. Called when the GPU (or its server) is deactivated. Paired with
    `resume_suspended_reservations_for_gpu`, which reschedules these once the GPU/server is
    reactivated -- reservations fully in the past by `now` are left untouched, since there's
    nothing left to suspend."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = select(Reservation).where(
        Reservation.gpu_id == gpu_id,
        Reservation.status == ReservationStatus.ACTIVE,
        Reservation.end_time > now,
    )
    reservations = list(session.execute(stmt).scalars().all())
    for reservation in reservations:
        reservation.status = ReservationStatus.SUSPENDED
    session.flush()
    return len(reservations)


def suspend_active_reservations_for_server(session: Session, server_id: int, now: datetime | None = None) -> int:
    """Same as `suspend_active_reservations_for_gpu`, but for every GPU on `server_id` -- used when
    the server itself (rather than one specific GPU) is deactivated."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = (
        select(Reservation)
        .join(GPU, Reservation.gpu_id == GPU.id)
        .where(
            GPU.server_id == server_id,
            Reservation.status == ReservationStatus.ACTIVE,
            Reservation.end_time > now,
        )
    )
    reservations = list(session.execute(stmt).scalars().all())
    for reservation in reservations:
        reservation.status = ReservationStatus.SUSPENDED
    session.flush()
    return len(reservations)


def _resume(reservations: list[Reservation], now: datetime, delay_minutes: int) -> None:
    """Reschedules each SUSPENDED reservation to start `delay_minutes` from `now` (reactivation
    time), keeping its original duration, and marks it ACTIVE again."""
    resume_start = now + timedelta(minutes=delay_minutes)
    for reservation in reservations:
        duration = reservation.end_time - reservation.start_time
        reservation.start_time = resume_start
        reservation.end_time = resume_start + duration
        reservation.status = ReservationStatus.ACTIVE


def resume_suspended_reservations_for_gpu(session: Session, gpu_id: int, now: datetime | None = None) -> int:
    """Resumes every SUSPENDED reservation on `gpu_id` -- called when the GPU (and its server) is
    reactivated. See `_resume` for the rescheduling rule."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = select(Reservation).where(Reservation.gpu_id == gpu_id, Reservation.status == ReservationStatus.SUSPENDED)
    reservations = list(session.execute(stmt).scalars().all())
    _resume(reservations, now, reactivation_delay_minutes(session))
    session.flush()
    return len(reservations)


def resume_suspended_reservations_for_server(session: Session, server_id: int, now: datetime | None = None) -> int:
    """Resumes every SUSPENDED reservation on `server_id`'s currently-active GPUs -- called when
    the server itself is reactivated. A GPU that's independently still deactivated
    (`GPU.is_active is False`) is left alone; it stays suspended until that GPU is reactivated too."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = (
        select(Reservation)
        .join(GPU, Reservation.gpu_id == GPU.id)
        .where(
            GPU.server_id == server_id,
            GPU.is_active.is_(True),
            Reservation.status == ReservationStatus.SUSPENDED,
        )
    )
    reservations = list(session.execute(stmt).scalars().all())
    _resume(reservations, now, reactivation_delay_minutes(session))
    session.flush()
    return len(reservations)


def list_reservations_for_gpu(
    session: Session,
    gpu_id: int,
    range_start: datetime,
    range_end: datetime,
    include_cancelled: bool = False,
) -> list[Reservation]:
    """Eager-loads `Reservation.user` (`joinedload`) since every caller reads `r.user.full_name`
    for chart rendering/summaries, some of them after the session that fetched the list has
    closed -- without this, that lazy load raises `DetachedInstanceError`.

    `include_cancelled` defaults off for the live booking chart, which must reflect only what's
    actually still reserved. Historical reports pass it on so past occupancy stays accurate even
    for reservations that were later cancelled (see chart_data.build_occupancy_chart, which clips
    a cancelled reservation's occupancy window to its `cancelled_at` time)."""
    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    stmt = select(Reservation).options(joinedload(Reservation.user)).where(
        Reservation.gpu_id == gpu_id,
        Reservation.start_time < range_end,
        Reservation.end_time > range_start,
    )
    if not include_cancelled:
        stmt = stmt.where(Reservation.status == ReservationStatus.ACTIVE)
    return list(session.execute(stmt).scalars().all())
