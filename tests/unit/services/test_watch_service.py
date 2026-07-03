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
