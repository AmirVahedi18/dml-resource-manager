from datetime import datetime, timedelta, timezone

import pytest

from dml_core.db.models.reservation import ReservationStatus
from dml_core.services import reservation_service as rs
from tests.factories import make_gpu, make_regulation, make_server, make_user

NOW = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=8)
END = START + timedelta(hours=2)


@pytest.fixture()
def setup(db_session):
    server = make_server(db_session)
    gpu = make_gpu(db_session, server, total_ram_mb=20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session)
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


def test_inactive_gpu_rejected(setup):
    session, gpu, regulation, user = setup
    gpu.is_active = False
    with pytest.raises(rs.GpuInactiveError):
        rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)


def test_gpu_on_inactive_server_rejected(setup):
    session, gpu, regulation, user = setup
    gpu.server.is_active = False
    with pytest.raises(rs.GpuInactiveError):
        rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)


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
    too_much = regulation.max_ram_per_reservation_gb * 1024 + 1
    with pytest.raises(rs.RamLimitExceededError):
        rs.create_reservation(session, user, gpu, START, END, too_much, regulation, now=NOW)


def test_ram_exceeds_gpu_total(setup):
    session, gpu, regulation, user = setup
    regulation.max_ram_per_reservation_gb = (gpu.total_ram_mb + 5000) // 1024
    with pytest.raises(rs.RamLimitExceededError):
        rs.create_reservation(session, user, gpu, START, END, gpu.total_ram_mb + 1, regulation, now=NOW)


def test_two_users_can_share_gpu_within_capacity(setup):
    session, gpu, regulation, user = setup
    other = make_user(session)
    rs.create_reservation(session, user, gpu, START, END, 8000, regulation, now=NOW)
    second = rs.create_reservation(session, other, gpu, START, END, 8000, regulation, now=NOW)
    assert second.id is not None


def test_capacity_exceeded_on_overlap(setup):
    session, gpu, regulation, user = setup
    other = make_user(session)
    rs.create_reservation(session, user, gpu, START, END, 15000, regulation, now=NOW)
    with pytest.raises(rs.CapacityExceededError):
        rs.create_reservation(session, other, gpu, START, END, 8000, regulation, now=NOW)


def test_non_overlapping_reservations_both_succeed_even_if_sum_exceeds_capacity(setup):
    session, gpu, regulation, user = setup
    other = make_user(session)
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


def test_user_with_multi_gpu_privilege_bypasses_one_gpu_restriction(setup):
    session, gpu, regulation, user = setup
    user.max_concurrent_gpus = 2
    server2 = make_server(session, name="server-2")
    gpu2 = make_gpu(session, server2, total_ram_mb=20000)
    rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    second = rs.create_reservation(session, user, gpu2, START, END, 4096, regulation, now=NOW)
    assert second.id is not None


def test_user_with_limit_2_can_hold_2_concurrent_reservations(setup):
    session, gpu, regulation, user = setup
    user.max_concurrent_gpus = 2
    server2 = make_server(session, name="server-2")
    gpu2 = make_gpu(session, server2, total_ram_mb=20000)
    server3 = make_server(session, name="server-3")
    gpu3 = make_gpu(session, server3, total_ram_mb=20000)

    rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    rs.create_reservation(session, user, gpu2, START, END, 4096, regulation, now=NOW)

    with pytest.raises(rs.ConcurrentGpuConflictError):
        rs.create_reservation(session, user, gpu3, START, END, 4096, regulation, now=NOW)


def test_user_with_limit_1_cannot_hold_2_concurrent_reservations(setup):
    session, gpu, regulation, user = setup
    assert user.max_concurrent_gpus == 1
    server2 = make_server(session, name="server-2")
    gpu2 = make_gpu(session, server2, total_ram_mb=20000)

    rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)

    with pytest.raises(rs.ConcurrentGpuConflictError):
        rs.create_reservation(session, user, gpu2, START, END, 4096, regulation, now=NOW)


def test_concurrent_gpu_limit_not_counted_twice_for_same_gpu(setup):
    session, gpu, regulation, user = setup
    user.max_concurrent_gpus = 1
    rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    later_start = END
    later_end = later_start + timedelta(hours=1)
    second = rs.create_reservation(session, user, gpu, later_start, later_end, 4096, regulation, now=NOW)
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
    other = make_user(session)
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


def test_slot_availability_reflects_partial_overlap(setup):
    session, gpu, regulation, user = setup
    # occupy only the first half-hour of a 1-hour window
    rs.create_reservation(session, user, gpu, START, START + timedelta(minutes=30), 8000, regulation, now=NOW)

    slots = rs.slot_availability(session, gpu, START, START + timedelta(hours=1), slot_minutes=30)

    naive_start = START.replace(tzinfo=None)
    assert len(slots) == 2
    assert slots[0] == (naive_start, gpu.total_ram_mb - 8000)
    assert slots[1] == (naive_start + timedelta(minutes=30), gpu.total_ram_mb)


def test_slot_availability_min_matches_min_free_ram_in_range(setup):
    session, gpu, regulation, user = setup
    other = make_user(session)
    rs.create_reservation(session, user, gpu, START, START + timedelta(minutes=30), 5000, regulation, now=NOW)
    rs.create_reservation(
        session, other, gpu, START + timedelta(minutes=30), START + timedelta(hours=1), 9000, regulation, now=NOW
    )

    slots = rs.slot_availability(session, gpu, START, START + timedelta(hours=1), slot_minutes=30)
    min_from_slots = min(free for _, free in slots)

    assert min_from_slots == rs.min_free_ram_in_range(session, gpu, START, START + timedelta(hours=1))


def test_cancel_all_for_user_on_server_cancels_only_that_users_reservations_there(setup):
    session, gpu, regulation, user = setup
    user.max_concurrent_gpus = 2
    other = make_user(session)
    other_server = make_server(session, "server-2")
    other_gpu = make_gpu(session, other_server)

    on_target_server = rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    other_users_on_target_server = rs.create_reservation(
        session, other, gpu, START + timedelta(hours=4), START + timedelta(hours=6), 4096, regulation, now=NOW
    )
    on_other_server = rs.create_reservation(
        session, user, other_gpu, START, END, 4096, regulation, now=NOW
    )

    cancelled_count = rs.cancel_all_for_user_on_server(session, user.id, gpu.server_id, now=NOW)

    assert cancelled_count == 1
    assert on_target_server.status == ReservationStatus.CANCELLED
    assert on_target_server.cancelled_at is not None
    assert other_users_on_target_server.status == ReservationStatus.ACTIVE
    assert on_other_server.status == ReservationStatus.ACTIVE


def test_suspend_active_reservations_for_gpu_only_touches_upcoming_ones(setup):
    session, gpu, regulation, user = setup
    upcoming = rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    already_ended = rs.create_reservation(
        session, user, gpu, NOW - timedelta(hours=3), NOW - timedelta(hours=1), 4096, regulation, now=NOW - timedelta(hours=4)
    )

    count = rs.suspend_active_reservations_for_gpu(session, gpu.id, now=NOW)

    assert count == 1
    assert upcoming.status == ReservationStatus.SUSPENDED
    assert already_ended.status == ReservationStatus.ACTIVE


def test_resume_suspended_reservations_for_gpu_reschedules_with_original_duration(setup):
    session, gpu, regulation, user = setup
    reservation = rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    duration = reservation.end_time - reservation.start_time

    rs.suspend_active_reservations_for_gpu(session, gpu.id, now=NOW)
    assert reservation.status == ReservationStatus.SUSPENDED

    reactivated_at = NOW + timedelta(hours=6)
    count = rs.resume_suspended_reservations_for_gpu(session, gpu.id, now=reactivated_at)

    assert count == 1
    assert reservation.status == ReservationStatus.ACTIVE
    assert reservation.start_time == (reactivated_at + timedelta(hours=1)).replace(tzinfo=None)
    assert reservation.end_time - reservation.start_time == duration


def test_resume_uses_configured_reactivation_delay(setup):
    session, gpu, regulation, user = setup
    # Non-default delay on the singleton Regulation row -- resume should honor it instead of 1h.
    regulation.reactivation_delay_minutes = 30
    session.flush()
    reservation = rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)

    rs.suspend_active_reservations_for_gpu(session, gpu.id, now=NOW)
    reactivated_at = NOW + timedelta(hours=6)
    rs.resume_suspended_reservations_for_gpu(session, gpu.id, now=reactivated_at)

    assert reservation.start_time == (reactivated_at + timedelta(minutes=30)).replace(tzinfo=None)


def test_reactivation_delay_minutes_defaults_without_regulation(db_session):
    # No singleton Regulation row -> defensive fallback keeps the historical 1h (60min) behavior.
    assert rs.reactivation_delay_minutes(db_session) == rs.DEFAULT_REACTIVATION_DELAY_MINUTES
    assert rs.DEFAULT_REACTIVATION_DELAY_MINUTES == 60


def test_reactivation_delay_minutes_reads_configured_value(db_session):
    make_regulation(db_session, reactivation_delay_minutes=45)
    assert rs.reactivation_delay_minutes(db_session) == 45


def test_suspend_and_resume_for_server_covers_all_its_gpus(db_session):
    server = make_server(db_session)
    gpu1 = make_gpu(db_session, server, index_on_server=0, total_ram_mb=20000)
    gpu2 = make_gpu(db_session, server, index_on_server=1, total_ram_mb=20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session, max_concurrent_gpus=2)

    r1 = rs.create_reservation(db_session, user, gpu1, START, END, 4096, regulation, now=NOW)
    r2 = rs.create_reservation(db_session, user, gpu2, START, END, 4096, regulation, now=NOW)

    suspended = rs.suspend_active_reservations_for_server(db_session, server.id, now=NOW)
    assert suspended == 2
    assert r1.status == ReservationStatus.SUSPENDED
    assert r2.status == ReservationStatus.SUSPENDED

    reactivated_at = NOW + timedelta(hours=2)
    resumed = rs.resume_suspended_reservations_for_server(db_session, server.id, now=reactivated_at)
    assert resumed == 2
    assert r1.status == ReservationStatus.ACTIVE
    assert r2.status == ReservationStatus.ACTIVE
    assert r1.start_time == (reactivated_at + timedelta(hours=1)).replace(tzinfo=None)


def test_resume_suspended_reservations_for_server_skips_still_inactive_gpu(db_session):
    server = make_server(db_session)
    gpu1 = make_gpu(db_session, server, index_on_server=0, total_ram_mb=20000)
    gpu2 = make_gpu(db_session, server, index_on_server=1, total_ram_mb=20000)
    regulation = make_regulation(db_session)
    user = make_user(db_session, max_concurrent_gpus=2)

    r1 = rs.create_reservation(db_session, user, gpu1, START, END, 4096, regulation, now=NOW)
    r2 = rs.create_reservation(db_session, user, gpu2, START, END, 4096, regulation, now=NOW)
    rs.suspend_active_reservations_for_server(db_session, server.id, now=NOW)

    gpu2.is_active = False  # independently still off even though the server is reactivating

    resumed = rs.resume_suspended_reservations_for_server(db_session, server.id, now=NOW + timedelta(hours=2))
    assert resumed == 1
    assert r1.status == ReservationStatus.ACTIVE
    assert r2.status == ReservationStatus.SUSPENDED


def test_count_active_reservations_includes_suspended(setup):
    session, gpu, regulation, user = setup
    rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    rs.suspend_active_reservations_for_gpu(session, gpu.id, now=NOW)

    assert rs.count_active_reservations(session, user.id, now=NOW) == 1


def test_cancel_reservation_can_cancel_a_suspended_one(setup):
    session, gpu, regulation, user = setup
    reservation = rs.create_reservation(session, user, gpu, START, END, 4096, regulation, now=NOW)
    rs.suspend_active_reservations_for_gpu(session, gpu.id, now=NOW)

    rs.cancel_reservation(session, reservation, now=NOW)
    assert reservation.status == ReservationStatus.CANCELLED
