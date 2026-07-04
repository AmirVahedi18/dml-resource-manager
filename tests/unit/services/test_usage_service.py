from datetime import datetime, timedelta, timezone

from dml_bot.services import reservation_service as rs
from dml_bot.services import usage_service as use
from tests.factories import make_gpu, make_regulation, make_server, make_user

NOW = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=8)
END = START + timedelta(hours=2)


def test_total_gpu_hours_by_user(db_session):
    server = make_server(db_session)
    gpu = make_gpu(db_session, server, total_ram_mb=20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session, telegram_id=1)
    rs.create_reservation(db_session, user, gpu, START, END, 4096, regulation, now=NOW)

    reservations = use.get_reservations_in_range(db_session, NOW, NOW + timedelta(days=1))
    totals = use.total_gpu_hours_by_user(reservations, NOW, NOW + timedelta(days=1))
    assert totals[user.id] == 2.0


def test_total_ram_hours_by_gpu(db_session):
    server = make_server(db_session)
    gpu = make_gpu(db_session, server, total_ram_mb=20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session, telegram_id=1)
    rs.create_reservation(db_session, user, gpu, START, END, 4096, regulation, now=NOW)

    reservations = use.get_reservations_in_range(db_session, NOW, NOW + timedelta(days=1))
    totals = use.total_ram_hours_by_gpu(reservations, NOW, NOW + timedelta(days=1))
    assert totals[gpu.id] == 2.0 * 4096


def test_range_clips_hours_partially_outside_window(db_session):
    server = make_server(db_session)
    gpu = make_gpu(db_session, server, total_ram_mb=20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session, telegram_id=1)
    rs.create_reservation(db_session, user, gpu, START, END, 4096, regulation, now=NOW)

    clipped_end = START + timedelta(hours=1)
    reservations = use.get_reservations_in_range(db_session, START, clipped_end)
    totals = use.total_gpu_hours_by_user(reservations, START, clipped_end)
    assert totals[user.id] == 1.0


def test_get_reservations_in_range_filters_by_server(db_session):
    server1 = make_server(db_session, name="server-1")
    server2 = make_server(db_session, name="server-2")
    gpu1 = make_gpu(db_session, server1, total_ram_mb=20000)
    gpu2 = make_gpu(db_session, server2, total_ram_mb=20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session, telegram_id=1, max_concurrent_gpus=2)
    rs.create_reservation(db_session, user, gpu1, START, END, 4096, regulation, now=NOW)
    rs.create_reservation(db_session, user, gpu2, START, END, 4096, regulation, now=NOW)

    reservations = use.get_reservations_in_range(
        db_session, NOW, NOW + timedelta(days=1), server_id=server1.id
    )
    assert [r.gpu_id for r in reservations] == [gpu1.id]
