from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_core.db.models.gpu import GPU
from dml_core.db.models.regulation import Regulation
from dml_core.db.models.reservation import Reservation
from dml_core.db.models.user import User
from dml_core.db.models.watch import WatchSubscription
from dml_core.services import reservation_service
from dml_core.services.reservation_service import min_free_ram_in_range
from dml_core.utils.time_utils import align_down_to_slot, floor_to_slot, to_naive_utc, utc_now


def create_watch(
    session: Session,
    user: User,
    gpu: GPU,
    range_start: datetime,
    range_end: datetime,
    min_ram_needed_mb: int,
    auto_book: bool = False,
) -> WatchSubscription:
    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    if range_end <= range_start:
        raise ValueError("range_end must be after range_start")
    watch = WatchSubscription(
        user_id=user.id,
        gpu_id=gpu.id,
        range_start=range_start,
        range_end=range_end,
        min_ram_needed_mb=min_ram_needed_mb,
        auto_book=auto_book,
    )
    session.add(watch)
    session.flush()
    return watch


def list_watches_for_user(session: Session, user_id: int, active_only: bool = True) -> list[WatchSubscription]:
    stmt = select(WatchSubscription).where(WatchSubscription.user_id == user_id)
    if active_only:
        stmt = stmt.where(WatchSubscription.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def cancel_watch(session: Session, watch: WatchSubscription) -> WatchSubscription:
    watch.is_active = False
    session.flush()
    return watch


def find_matching_watches(session: Session, gpu: GPU, now: datetime | None = None) -> list[WatchSubscription]:
    """Active, unexpired, not-yet-notified watches on `gpu` whose range now has enough free RAM."""
    now = to_naive_utc(now) if now else utc_now()
    stmt = select(WatchSubscription).where(
        WatchSubscription.gpu_id == gpu.id,
        WatchSubscription.is_active.is_(True),
        WatchSubscription.notified_at.is_(None),
        WatchSubscription.range_end > now,
    )
    candidates = session.execute(stmt).scalars().all()

    matches = []
    for watch in candidates:
        window_start = max(watch.range_start, now)
        free_ram = min_free_ram_in_range(session, gpu, window_start, watch.range_end)
        if free_ram >= watch.min_ram_needed_mb:
            matches.append(watch)
    return matches


def attempt_auto_book(
    session: Session,
    watch: WatchSubscription,
    gpu: GPU,
    regulation: Regulation,
    now: datetime | None = None,
) -> Reservation | None:
    """Tries to book the just-freed window for `watch`'s owner: from whenever it frees through
    `watch.range_end`, capped by the regulation's max duration, at `watch.min_ram_needed_mb`.
    Reuses `reservation_service.create_reservation` for every check (slot alignment, RAM/
    duration/booking-horizon limits, per-user active-reservation cap, concurrent-GPU conflict) so
    this adds no validation rules of its own -- if any of them reject the attempt (e.g. the
    student is already at their active-reservation limit), returns None so the caller can fall
    back to a plain notification instead of silently failing."""
    now = to_naive_utc(now) if now else utc_now()
    slot_minutes = regulation.min_reservation_slot_minutes
    window_start = floor_to_slot(max(watch.range_start, now), slot_minutes)
    max_end = window_start + timedelta(hours=regulation.max_duration_hours)
    window_end = align_down_to_slot(min(watch.range_end, max_end), slot_minutes)
    if window_end <= window_start:
        return None

    user = session.get(User, watch.user_id)
    try:
        return reservation_service.create_reservation(
            session, user, gpu, window_start, window_end, watch.min_ram_needed_mb, regulation, now=now
        )
    except reservation_service.ReservationError:
        return None


def mark_notified(session: Session, watch: WatchSubscription, now: datetime | None = None) -> WatchSubscription:
    watch.notified_at = to_naive_utc(now) if now else utc_now()
    watch.is_active = False
    session.flush()
    return watch
