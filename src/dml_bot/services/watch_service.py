from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.user import User
from dml_bot.db.models.watch import WatchSubscription
from dml_bot.services.reservation_service import min_free_ram_in_range
from dml_bot.utils.time_utils import to_naive_utc, utc_now


def create_watch(
    session: Session,
    user: User,
    gpu: GPU,
    range_start: datetime,
    range_end: datetime,
    min_ram_needed_mb: int,
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


def mark_notified(session: Session, watch: WatchSubscription, now: datetime | None = None) -> WatchSubscription:
    watch.notified_at = to_naive_utc(now) if now else utc_now()
    watch.is_active = False
    session.flush()
    return watch
