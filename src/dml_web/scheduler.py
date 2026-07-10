"""Background jobs for the web backend -- started from the FastAPI lifespan in main.py.

Only one job matters here: auto-booking matched watches. Web only ever creates auto-book watches
(see routers/watches.py -- there's no notification channel to fall back to a plain "just notify"
for), so a watch that can't be auto-booked right now (e.g. the student is temporarily at their
active-reservation cap) is left active and retried next cycle instead of being consumed --
`watch_service.find_matching_watches` already filters to `notified_at IS NULL`, so an unbooked
match just resurfaces on the next poll.

A stale-watch cleanup job is also included (same retention-based prune of long-since-consumed
`WatchSubscription` rows; `Reservation` rows are never deleted -- kept forever for historical
availability lookback).
"""
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_core.config.schema import AppConfig
from dml_core.db.models.watch import WatchSubscription
from dml_core.db.session import session_scope
from dml_core.services import regulation_service, server_service, watch_service
from dml_core.utils.time_utils import utc_now


def run_watch_autobook_check(session: Session) -> int:
    booked = 0
    regulation = regulation_service.get_regulation(session)
    for server in server_service.list_servers(session):
        for gpu in server_service.list_gpus(session, server):
            for watch in watch_service.find_matching_watches(session, gpu):
                reservation = watch_service.attempt_auto_book(session, watch, gpu, regulation)
                if reservation is not None:
                    watch_service.mark_notified(session, watch)
                    booked += 1
    return booked


def run_cleanup(session: Session, retention_days: int) -> int:
    cutoff = utc_now() - timedelta(days=retention_days)
    stale = session.execute(
        select(WatchSubscription).where(
            WatchSubscription.is_active.is_(False), WatchSubscription.created_at < cutoff
        )
    ).scalars().all()
    for watch in stale:
        session.delete(watch)
    session.flush()
    return len(stale)


def build_scheduler(app_cfg: AppConfig) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    def watch_job() -> None:
        with session_scope() as session:
            run_watch_autobook_check(session)

    def cleanup_job() -> None:
        with session_scope() as session:
            run_cleanup(session, app_cfg.scheduler.cleanup_retention_days)

    scheduler.add_job(
        watch_job, "interval", seconds=app_cfg.scheduler.poll_interval_seconds, id="web_watch_autobook"
    )
    scheduler.add_job(cleanup_job, "interval", hours=24, id="web_cleanup")
    return scheduler
