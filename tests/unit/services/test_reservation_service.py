from datetime import datetime, timedelta, timezone

import pytest

from dml_bot.services import reservation_service as rs
from tests.factories import make_gpu, make_regulation, make_server, make_user

NOW = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=8)
END = START + timedelta(hours=2)


@pytest.fixture()
def setup(db_session):
    server = make_server(db_session)
    gpu = make_gpu(db_session, server, total_ram_mb=20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session, telegram_id=1)
    return db_session, gpu, regulation, user


def test_create_reservation_success(setup):
    session, gpu, regulation, user = setup
    reservation = rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    assert reservation.id is not None
    assert reservation.ram_mb == 4096


def test_slot_alignment_rejected(setup):
    session, gpu, regulation, user = setup
    bad_start = START + timedelta(minutes=5)
    with pytest.raises(rs.SlotAlignmentError):
        rs.create_reservation(session, user, gpu, bad_start, END, 4096, regulation, now=NOW)


def test_duration_exceeded(setup):
    session, gpu, regulation, user = setup
    too_long_end = START + timedelta(hours=regulation.max_duration_hours + 1)
    with pytest.raises(rs.DurationExceededError):
        rs.create_reservation(session, user, gpu, START, too_long_end, 4096, regulation, now=NOW)


def test_start_in_the_past_rejected(setup):
    session, gpu, regulation, user = setup
    past_start = NOW - timedelta(hours=1)
    past_end = NOW - timedelta(minutes=30)
    with pytest.raises(rs.OutsideBookingHorizonError):
        rs.create_reservation(session, user, gpu, past_start, past_end, 4096, regulation, now=NOW)


def test_start_beyond_booking_horizon_rejected(setup):
    session, gpu, regulation, user = setup
    far_start = NOW + timedelta(days=regulation.booking_horizon_days + 1)
    far_end = far_start + timedelta(hours=1)
    with pytest.raises(rs.OutsideBookingHorizonError):
        rs.create_reservation(session, user, gpu, far_start, far_end, 4096, regulation, now=NOW)


def test_ram_exceeds_regulation_limit(setup):
    session, gpu, regulation, user = setup
    too_much = regulation.max_ram_per_reservation_mb + 1
    with pytest.raises(rs.RamLimitExceededError):
        rs.create_reservation(session, user, gpu, START, END, too_much, regulation, now=NOW)


def test_ram_exceeds_gpu_total(setup):
    session, gpu, regulation, user = setup
    regulation.max_ram_per_reservation_mb = gpu.total_ram_mb + 5000
    with pytest.raises(rs.RamLimitExceededError):
        rs.create_reservation(session, user, gpu, START, END, gpu.total_ram_mb + 1, regulation, now=NOW)


def test_two_users_can_share_gpu_within_capacity(setup):
    session, gpu, regulation, user = setup
    other = make_user(session, telegram_id=2)
    rs.create_reservation(session, user, gpu, START, END, 8000, regulation, now=NOW)
    second = rs.create_reservation(session, other, gpu, START, END, 8000, regulation, now=NOW)
    assert second.id is not None


def test_capacity_exceeded_on_overlap(setup):
    session, gpu, regulation, user = setup
    other = make_user(session, telegram_id=2)
    rs.create_reservation(session, user, gpu, START, END, 15000, regulation, now=NOW)
    with pytest.raises(rs.CapacityExceededError):
        rs.create_reservation(session, other, gpu, START, END, 8000, regulation, now=NOW)


def test_non_overlapping_reservations_both_succeed_even_if_sum_exceeds_capacity(setup):
    session, gpu, regulation, user = setup
    other = make_user(session, telegram_id=2)
    rs.create_reservation(session, user, gpu, START, END, 15000, regulation, now=NOW)
    later_start = END
    later_end = later_start + timedelta(hours=1)
    second = rs.create_reservation(session, other, gpu, later_start, later_end, 15000, regulation, now=NOW)
    assert second.id is not None


def test_one_gpu_per_user_restriction(setup):
    session, gpu, regulation, user = setup
    server2 = make_server(session, name="server-2")
    gpu2 = make_gpu(session, server2, total_ram_mb=20000)
    rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    with pytest.raises(rs.ConcurrentGpuConflictError):
        rs.create_reservation(session, user, gpu2, START, END, 4096, regulation, now=NOW)


def test_privileged_user_bypasses_one_gpu_restriction(setup):
    session, gpu, regulation, user = setup
    user.can_use_multiple_gpus = True
    server2 = make_server(session, name="server-2")
    gpu2 = make_gpu(session, server2, total_ram_mb=20000)
    rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    second = rs.create_reservation(session, user, gpu2, START, END, 4096, regulation, now=NOW)
    assert second.id is not None


def test_max_active_reservations_limit(setup):
    session, gpu, regulation, user = setup
    regulation.max_active_reservations_per_user = 1
    rs.create_reservation(session, user, gpu, START, END, 1000, regulation, now=NOW)
    later_start = END
    later_end = later_start + timedelta(hours=1)
    with pytest.raises(rs.ActiveReservationLimitError):
        rs.create_reservation(session, user, gpu, later_start, later_end, 1000, regulation, now=NOW)


def test_cancel_reservation_frees_capacity(setup):
    session, gpu, regulation, user = setup
    other = make_user(session, telegram_id=2)
    reservation = rs.create_reservation(session, user, gpu, START, END, 15000, regulation, now=NOW)
    rs.cancel_reservation(session, reservation, now=NOW)
    second = rs.create_reservation(session, other, gpu, START, END, 15000, regulation, now=NOW)
    assert second.id is not None


def test_cancel_already_cancelled_raises(setup):
    session, gpu, regulation, user = setup
    reservation = rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    rs.cancel_reservation(session, reservation, now=NOW)
    with pytest.raises(rs.ReservationError):
        rs.cancel_reservation(session, reservation, now=NOW)


def test_min_free_ram_in_range(setup):
    session, gpu, regulation, user = setup
    rs.create_reservation(session, user, gpu, START, END, 8000, regulation, now=NOW)
    free = rs.min_free_ram_in_range(session, gpu, START, END)
    assert free == gpu.total_ram_mb - 8000
