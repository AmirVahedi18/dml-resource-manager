from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun import freeze_time

from dml_bot.db.models.reservation import Reservation
from dml_bot.scheduling import jobs
from dml_bot.services import reservation_service, watch_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.factories import make_gpu, make_regulation, make_server, make_user


class StubBot:
    def __init__(self):
        self.send_message = AsyncMock(return_value=None)


def _setup(db_session, total_ram_mb=20000):
    server = make_server(db_session)
    gpu = make_gpu(db_session, server, total_ram_mb=total_ram_mb)
    regulation = make_regulation(db_session, max_ram_per_reservation_mb=total_ram_mb)
    occupier = make_user(db_session, telegram_id=1, full_name="Occupier")
    return server, gpu, regulation, occupier


async def test_run_watch_check_notifies_and_marks_notified(db_session):
    server, gpu, regulation, occupier = _setup(db_session)
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=8)
    end = start + timedelta(hours=2)
    reservation = reservation_service.create_reservation(
        db_session, occupier, gpu, start, end, gpu.total_ram_mb, regulation
    )

    watcher = make_user(db_session, telegram_id=2, full_name="Watcher")
    watch = watch_service.create_watch(db_session, watcher, gpu, start, end, 1000)

    bot = StubBot()
    sent = await jobs.run_watch_check(db_session, bot, "UTC")
    assert sent == 0
    bot.send_message.assert_not_awaited()

    reservation_service.cancel_reservation(db_session, reservation)
    sent = await jobs.run_watch_check(db_session, bot, "UTC")
    assert sent == 1
    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args.kwargs["chat_id"] == watcher.telegram_id
    assert watch.notified_at is not None

    # second run should not re-notify
    sent_again = await jobs.run_watch_check(db_session, bot, "UTC")
    assert sent_again == 0
    bot.send_message.assert_awaited_once()


async def test_run_watch_check_auto_books_when_enabled(db_session):
    server, gpu, regulation, occupier = _setup(db_session)
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=8)
    end = start + timedelta(hours=2)
    reservation = reservation_service.create_reservation(
        db_session, occupier, gpu, start, end, gpu.total_ram_mb, regulation
    )

    watcher = make_user(db_session, telegram_id=2, full_name="Watcher")
    watch_service.create_watch(db_session, watcher, gpu, start, end, 1000, auto_book=True)

    reservation_service.cancel_reservation(db_session, reservation)
    bot = StubBot()
    sent = await jobs.run_watch_check(db_session, bot, "UTC")

    assert sent == 1
    assert bot.send_message.call_args.kwargs["chat_id"] == watcher.telegram_id
    assert "Auto-booked" in bot.send_message.call_args.kwargs["text"]
    booked = reservation_service.list_active_reservations_for_user(db_session, watcher.id)
    assert len(booked) == 1
    assert booked[0].start_time == start


async def test_run_watch_check_falls_back_to_notify_when_auto_book_fails(db_session):
    server, gpu, regulation, occupier = _setup(db_session)
    regulation.max_active_reservations_per_user = 1
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=8)
    end = start + timedelta(hours=2)
    reservation = reservation_service.create_reservation(
        db_session, occupier, gpu, start, end, gpu.total_ram_mb, regulation
    )

    watcher = make_user(db_session, telegram_id=2, full_name="Watcher")
    other_gpu = make_gpu(db_session, server, index_on_server=1)
    reservation_service.create_reservation(db_session, watcher, other_gpu, start, end, 1000, regulation)
    watch_service.create_watch(db_session, watcher, gpu, start, end, 1000, auto_book=True)

    reservation_service.cancel_reservation(db_session, reservation)
    bot = StubBot()
    sent = await jobs.run_watch_check(db_session, bot, "UTC")

    assert sent == 1
    assert "Auto-booked" not in bot.send_message.call_args.kwargs["text"]
    assert "Free GPU capacity" in bot.send_message.call_args.kwargs["text"]
    assert reservation_service.count_active_reservations(db_session, watcher.id) == 1


async def test_run_reminder_check_sends_once(db_session):
    server, gpu, regulation, occupier = _setup(db_session)
    start = floor_to_slot(utc_now(), 30)  # next aligned slot, at most 30 min away
    if start <= utc_now():
        start += timedelta(minutes=30)
    end = start + timedelta(hours=1)
    reservation_service.create_reservation(db_session, occupier, gpu, start, end, 4096, regulation)

    bot = StubBot()
    sent = await jobs.run_reminder_check(db_session, bot, "UTC", lead_minutes=35)
    assert sent == 1
    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args.kwargs["chat_id"] == occupier.telegram_id

    sent_again = await jobs.run_reminder_check(db_session, bot, "UTC", lead_minutes=35)
    assert sent_again == 0
    bot.send_message.assert_awaited_once()


async def test_run_reminder_check_ignores_far_future_reservations(db_session):
    server, gpu, regulation, occupier = _setup(db_session)
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=5)
    end = start + timedelta(hours=1)
    reservation_service.create_reservation(db_session, occupier, gpu, start, end, 4096, regulation)

    bot = StubBot()
    sent = await jobs.run_reminder_check(db_session, bot, "UTC", lead_minutes=15)
    assert sent == 0
    bot.send_message.assert_not_awaited()


def test_run_cleanup_keeps_reservations_forever_but_deletes_stale_watches(db_session):
    server, gpu, regulation, occupier = _setup(db_session)

    far_past_now = utc_now() - timedelta(days=40)
    start = floor_to_slot(far_past_now, 30) + timedelta(hours=1)
    end = start + timedelta(hours=1)
    reservation = reservation_service.create_reservation(
        db_session, occupier, gpu, start, end, 4096, regulation, now=far_past_now
    )
    reservation_id = reservation.id

    watcher = make_user(db_session, telegram_id=3, full_name="Watcher2")
    stale_watch = watch_service.create_watch(db_session, watcher, gpu, start, end, 1000)
    with freeze_time(far_past_now.isoformat()):
        watch_service.cancel_watch(db_session, stale_watch)
    stale_watch.created_at = far_past_now
    db_session.flush()

    deleted = jobs.run_cleanup(db_session, retention_days=30)
    assert deleted == 1  # only the stale watch -- reservations are never deleted by cleanup

    # The 40-day-old reservation is still there for historical availability charts to read.
    assert db_session.get(Reservation, reservation_id) is not None
