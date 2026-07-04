from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_bot.bot.formatting import reservation_summary, watch_summary
from dml_bot.config.schema import AppConfig
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.reservation import Reservation, ReservationStatus
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, server_service, watch_service
from dml_bot.utils.time_utils import utc_now


async def run_watch_check(session: Session, bot, tz_name: str) -> int:
    sent = 0
    regulation = regulation_service.get_regulation(session)
    for server in server_service.list_servers(session):
        for gpu in server_service.list_gpus(session, server):
            for watch in watch_service.find_matching_watches(session, gpu):
                user = session.get(User, watch.user_id)
                reservation = (
                    watch_service.attempt_auto_book(session, watch, gpu, regulation) if watch.auto_book else None
                )
                if reservation is not None:
                    text = "🎉 Auto-booked your freed-up reservation!\n\n" + reservation_summary(
                        reservation, gpu, server, tz_name
                    )
                else:
                    text = "🔔 Free GPU capacity available!\n\n" + watch_summary(watch, gpu, server, tz_name)
                await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="HTML")
                watch_service.mark_notified(session, watch)
                sent += 1
    return sent


async def run_reminder_check(session: Session, bot, tz_name: str, lead_minutes: int) -> int:
    now = utc_now()
    window_end = now + timedelta(minutes=lead_minutes)
    stmt = select(Reservation).where(
        Reservation.status == ReservationStatus.ACTIVE,
        Reservation.reminded_at.is_(None),
        Reservation.start_time > now,
        Reservation.start_time <= window_end,
    )
    reservations = session.execute(stmt).scalars().all()

    sent = 0
    for reservation in reservations:
        user = session.get(User, reservation.user_id)
        gpu = session.get(GPU, reservation.gpu_id)
        text = "⏰ Your reservation starts soon!\n\n" + reservation_summary(reservation, gpu, gpu.server, tz_name)
        await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="HTML")
        reservation.reminded_at = now
        sent += 1
    session.flush()
    return sent


def run_cleanup(session: Session, retention_days: int) -> int:
    """Deletes long-since-consumed `WatchSubscription` rows only. `Reservation` rows are kept
    forever -- admins can review a GPU's historical availability indefinitely via Usage Report's
    📅 Historical Availability screen, which needs the full history to still be there."""
    from dml_bot.db.models.watch import WatchSubscription

    cutoff = utc_now() - timedelta(days=retention_days)
    deleted = 0

    stale_watches = session.execute(
        select(WatchSubscription).where(
            WatchSubscription.is_active.is_(False), WatchSubscription.created_at < cutoff
        )
    ).scalars().all()
    for watch in stale_watches:
        session.delete(watch)
        deleted += 1

    session.flush()
    return deleted


def build_scheduler(bot, config: AppConfig) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    tz_name = config.bot.timezone

    async def watch_job():
        with session_scope() as session:
            await run_watch_check(session, bot, tz_name)

    async def reminder_job():
        with session_scope() as session:
            await run_reminder_check(session, bot, tz_name, config.scheduler.reminder_minutes_before)

    async def cleanup_job():
        with session_scope() as session:
            run_cleanup(session, config.scheduler.cleanup_retention_days)

    interval = config.scheduler.poll_interval_seconds
    scheduler.add_job(watch_job, "interval", seconds=interval, id="watch_check")
    scheduler.add_job(reminder_job, "interval", seconds=interval, id="reminder_check")
    scheduler.add_job(cleanup_job, "interval", hours=24, id="cleanup")
    return scheduler
