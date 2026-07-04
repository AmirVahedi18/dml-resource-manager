from datetime import datetime, timedelta, timezone

from dml_bot.services import reservation_service as rs
from dml_bot.services import watch_service as ws
from tests.factories import make_gpu, make_regulation, make_server, make_user

NOW = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=8)
END = START + timedelta(hours=2)


def _setup(db_session, total_ram_mb=20000):
    server = make_server(db_session)
    gpu = make_gpu(db_session, server, total_ram_mb=total_ram_mb)
    regulation = make_regulation(db_session, max_ram_per_reservation_mb=total_ram_mb)
    user = make_user(db_session, telegram_id=1)
    return gpu, regulation, user


def test_watch_does_not_match_when_gpu_full(db_session):
    gpu, regulation, user = _setup(db_session)
    occupier = make_user(db_session, telegram_id=2)
    rs.create_reservation(db_session, occupier, gpu, START, END, gpu.total_ram_mb, regulation, now=NOW)

    watcher = make_user(db_session, telegram_id=3)
    ws.create_watch(db_session, watcher, gpu, START, END, 1000)

    assert ws.find_matching_watches(db_session, gpu, now=NOW) == []


def test_watch_matches_after_cancellation_frees_capacity(db_session):
    gpu, regulation, user = _setup(db_session)
    occupier = make_user(db_session, telegram_id=2)
    reservation = rs.create_reservation(
        db_session, occupier, gpu, START, END, gpu.total_ram_mb, regulation, now=NOW
    )

    watcher = make_user(db_session, telegram_id=3)
    watch = ws.create_watch(db_session, watcher, gpu, START, END, 1000)
    assert ws.find_matching_watches(db_session, gpu, now=NOW) == []

    rs.cancel_reservation(db_session, reservation, now=NOW)
    matches = ws.find_matching_watches(db_session, gpu, now=NOW)
    assert [m.id for m in matches] == [watch.id]


def test_mark_notified_deactivates_watch(db_session):
    gpu, regulation, user = _setup(db_session)
    watch = ws.create_watch(db_session, user, gpu, START, END, 1000)
    ws.mark_notified(db_session, watch, now=NOW)
    assert watch.is_active is False
    assert watch.notified_at is not None


def test_cancel_watch(db_session):
    gpu, regulation, user = _setup(db_session)
    watch = ws.create_watch(db_session, user, gpu, START, END, 1000)
    ws.cancel_watch(db_session, watch)
    assert ws.list_watches_for_user(db_session, user.id) == []


def test_attempt_auto_book_books_the_freed_window(db_session):
    gpu, regulation, user = _setup(db_session)
    range_end = NOW + timedelta(hours=5)  # shorter than the 12h regulation cap
    watch = ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, auto_book=True)

    reservation = ws.attempt_auto_book(db_session, watch, gpu, regulation, now=NOW)

    assert reservation is not None
    assert reservation.user_id == user.id
    assert reservation.start_time == NOW.replace(tzinfo=None)
    assert reservation.end_time == range_end.replace(tzinfo=None)
    assert reservation.ram_mb == 1000


def test_attempt_auto_book_caps_duration_to_regulation_max(db_session):
    gpu, regulation, user = _setup(db_session)
    range_end = NOW + timedelta(hours=20)  # longer than the 12h regulation cap
    watch = ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, auto_book=True)

    reservation = ws.attempt_auto_book(db_session, watch, gpu, regulation, now=NOW)

    assert reservation is not None
    assert reservation.start_time == NOW.replace(tzinfo=None)
    assert reservation.end_time == (NOW + timedelta(hours=regulation.max_duration_hours)).replace(tzinfo=None)


def test_attempt_auto_book_returns_none_when_window_too_short(db_session):
    gpu, regulation, user = _setup(db_session)
    range_end = NOW + timedelta(minutes=10)  # less than one 30-minute slot
    watch = ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, auto_book=True)

    assert ws.attempt_auto_book(db_session, watch, gpu, regulation, now=NOW) is None


def test_attempt_auto_book_returns_none_when_reservation_limit_reached(db_session):
    gpu, regulation, user = _setup(db_session)
    regulation.max_active_reservations_per_user = 1
    other_gpu = make_gpu(db_session, gpu.server, index_on_server=1)
    rs.create_reservation(db_session, user, other_gpu, START, END, 1000, regulation, now=NOW)

    range_end = NOW + timedelta(hours=5)
    watch = ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, auto_book=True)

    assert ws.attempt_auto_book(db_session, watch, gpu, regulation, now=NOW) is None
    assert rs.count_active_reservations(db_session, user.id, now=NOW) == 1
