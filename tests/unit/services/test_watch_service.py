from datetime import datetime, timedelta, timezone

import pytest

from dml_core.db.models.watch import WatchSubscription
from dml_core.services import reservation_service as rs
from dml_core.services import watch_service as ws
from tests.factories import make_gpu, make_regulation, make_server, make_user

NOW = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=8)
END = START + timedelta(hours=2)


def _setup(db_session, total_ram_mb=20000):
    server = make_server(db_session)
    gpu = make_gpu(db_session, server, total_ram_mb=total_ram_mb)
    # Round the GB cap up so it can still cover a full-GPU reservation (used to simulate the
    # GPU being fully occupied), even though total_ram_mb isn't necessarily a multiple of 1024.
    regulation = make_regulation(db_session, max_ram_per_reservation_gb=-(-total_ram_mb // 1024))
    user = make_user(db_session)
    return gpu, regulation, user


def test_watch_does_not_match_when_gpu_full(db_session):
    gpu, regulation, user = _setup(db_session)
    occupier = make_user(db_session)
    rs.create_reservation(db_session, occupier, gpu, START, END, gpu.total_ram_mb, regulation, now=NOW)

    watcher = make_user(db_session)
    ws.create_watch(db_session, watcher, gpu, START, END, 1000, regulation)

    assert ws.find_matching_watches(db_session, gpu, now=NOW) == []


def test_watch_matches_after_cancellation_frees_capacity(db_session):
    gpu, regulation, user = _setup(db_session)
    occupier = make_user(db_session)
    reservation = rs.create_reservation(
        db_session, occupier, gpu, START, END, gpu.total_ram_mb, regulation, now=NOW
    )

    watcher = make_user(db_session)
    watch = ws.create_watch(db_session, watcher, gpu, START, END, 1000, regulation)
    assert ws.find_matching_watches(db_session, gpu, now=NOW) == []

    rs.cancel_reservation(db_session, reservation, now=NOW)
    matches = ws.find_matching_watches(db_session, gpu, now=NOW)
    assert [m.id for m in matches] == [watch.id]


def test_mark_notified_deactivates_watch(db_session):
    gpu, regulation, user = _setup(db_session)
    watch = ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)
    ws.mark_notified(db_session, watch, now=NOW)
    assert watch.is_active is False
    assert watch.notified_at is not None


def test_cancel_watch(db_session):
    gpu, regulation, user = _setup(db_session)
    watch = ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)
    ws.cancel_watch(db_session, watch)
    assert ws.list_watches_for_user(db_session, user.id) == []


def test_create_watch_rejects_inactive_gpu(db_session):
    gpu, regulation, user = _setup(db_session)
    gpu.is_active = False
    with pytest.raises(ws.GpuInactiveError):
        ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)


def test_create_watch_rejects_gpu_on_inactive_server(db_session):
    gpu, regulation, user = _setup(db_session)
    gpu.server.is_active = False
    with pytest.raises(ws.GpuInactiveError):
        ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)


def test_create_watch_rejects_duration_exceeding_regulation_max(db_session):
    gpu, regulation, user = _setup(db_session)
    range_end = NOW + timedelta(hours=regulation.max_duration_hours + 1)
    with pytest.raises(rs.DurationExceededError):
        ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, regulation)


def test_create_watch_allows_duration_equal_to_regulation_max(db_session):
    gpu, regulation, user = _setup(db_session)
    range_end = NOW + timedelta(hours=regulation.max_duration_hours)
    ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, regulation)


def test_create_watch_rejects_ram_exceeding_regulation_cap(db_session):
    gpu, regulation, user = _setup(db_session)
    over_cap_mb = regulation.max_ram_per_reservation_gb * 1024 + 1
    with pytest.raises(rs.RamLimitExceededError):
        ws.create_watch(db_session, user, gpu, START, END, over_cap_mb, regulation)


def test_create_watch_rejects_non_positive_ram(db_session):
    gpu, regulation, user = _setup(db_session)
    with pytest.raises(rs.RamLimitExceededError):
        ws.create_watch(db_session, user, gpu, START, END, 0, regulation)


def test_create_watch_rejects_overlapping_watch_for_same_user(db_session):
    gpu, regulation, user = _setup(db_session)
    other_gpu = make_gpu(db_session, gpu.server, index_on_server=1)
    ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)

    with pytest.raises(ws.OverlappingWatchError):
        ws.create_watch(db_session, user, other_gpu, START + timedelta(minutes=30), END + timedelta(minutes=30), 1000, regulation)


def test_create_watch_allows_non_overlapping_watch_for_same_user(db_session):
    gpu, regulation, user = _setup(db_session)
    ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)
    ws.create_watch(db_session, user, gpu, END, END + timedelta(hours=1), 1000, regulation)


def test_create_watch_allows_overlapping_watch_for_different_user(db_session):
    gpu, regulation, user = _setup(db_session)
    other_user = make_user(db_session)
    ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)
    ws.create_watch(db_session, other_user, gpu, START, END, 1000, regulation)


def test_create_watch_ignores_cancelled_watch_when_checking_overlap(db_session):
    gpu, regulation, user = _setup(db_session)
    watch = ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)
    ws.cancel_watch(db_session, watch)
    ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)


def test_attempt_auto_book_books_the_freed_window(db_session):
    gpu, regulation, user = _setup(db_session)
    range_end = NOW + timedelta(hours=5)  # shorter than the 12h regulation cap
    watch = ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, regulation, auto_book=True)

    reservation = ws.attempt_auto_book(db_session, watch, gpu, regulation, now=NOW)

    assert reservation is not None
    assert reservation.user_id == user.id
    assert reservation.start_time == NOW.replace(tzinfo=None)
    assert reservation.end_time == range_end.replace(tzinfo=None)
    assert reservation.ram_mb == 1000


def test_attempt_auto_book_caps_duration_to_regulation_max(db_session):
    """A watch this long could never be created via `create_watch` anymore (it exceeds the
    regulation's max duration), but `attempt_auto_book`'s cap is kept as a defensive safety net --
    construct one directly, bypassing validation, to confirm the cap still holds."""
    gpu, regulation, user = _setup(db_session)
    range_end = NOW + timedelta(hours=20)  # longer than the 12h regulation cap
    watch = WatchSubscription(
        user_id=user.id,
        gpu_id=gpu.id,
        range_start=NOW.replace(tzinfo=None),
        range_end=range_end.replace(tzinfo=None),
        min_ram_needed_mb=1000,
        auto_book=True,
        description="",
    )
    db_session.add(watch)
    db_session.flush()

    reservation = ws.attempt_auto_book(db_session, watch, gpu, regulation, now=NOW)

    assert reservation is not None
    assert reservation.start_time == NOW.replace(tzinfo=None)
    assert reservation.end_time == (NOW + timedelta(hours=regulation.max_duration_hours)).replace(tzinfo=None)


def test_attempt_auto_book_returns_none_when_window_too_short(db_session):
    gpu, regulation, user = _setup(db_session)
    range_end = NOW + timedelta(minutes=10)  # less than one 30-minute slot
    watch = ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, regulation, auto_book=True)

    assert ws.attempt_auto_book(db_session, watch, gpu, regulation, now=NOW) is None


def test_list_watches_returns_all_users_watches(db_session):
    gpu, regulation, user = _setup(db_session)
    other_user = make_user(db_session)
    ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)
    ws.create_watch(db_session, other_user, gpu, START, END, 1000, regulation)

    watches = ws.list_watches(db_session)
    assert len(watches) == 2
    assert ws.count_watches(db_session) == 2


def test_list_watches_filters_by_user_gpu_and_server(db_session):
    gpu, regulation, user = _setup(db_session)
    other_server_gpu = make_gpu(db_session, make_server(db_session, name="server-2"), index_on_server=0)
    other_user = make_user(db_session)

    w1 = ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)
    w2 = ws.create_watch(db_session, other_user, gpu, START, END, 1000, regulation)
    # Same user as w1 but a non-overlapping window -- the overlap guard is per-user regardless of GPU.
    w3 = ws.create_watch(db_session, user, other_server_gpu, END, END + timedelta(hours=1), 1000, regulation)

    assert {w.id for w in ws.list_watches(db_session, user_id=user.id)} == {w1.id, w3.id}
    assert ws.count_watches(db_session, user_id=user.id) == 2

    assert {w.id for w in ws.list_watches(db_session, gpu_id=gpu.id)} == {w1.id, w2.id}
    assert ws.count_watches(db_session, gpu_id=gpu.id) == 2

    assert ws.count_watches(db_session, server_id=gpu.server_id) == 2


def test_list_watches_includes_cancelled_and_matched(db_session):
    gpu, regulation, user = _setup(db_session)
    watch = ws.create_watch(db_session, user, gpu, START, END, 1000, regulation)
    ws.cancel_watch(db_session, watch)

    watches = ws.list_watches(db_session)
    assert len(watches) == 1
    assert watches[0].is_active is False


def test_list_watches_paginated(db_session):
    gpu, regulation, user = _setup(db_session)
    for i in range(5):
        ws.create_watch(
            db_session, user, gpu, START + timedelta(hours=i * 3), END + timedelta(hours=i * 3), 1000, regulation
        )

    assert ws.count_watches(db_session) == 5
    assert len(ws.list_watches(db_session, limit=2, offset=0)) == 2
    assert len(ws.list_watches(db_session, limit=2, offset=4)) == 1


def test_attempt_auto_book_returns_none_when_reservation_limit_reached(db_session):
    gpu, regulation, user = _setup(db_session)
    regulation.max_active_reservations_per_user = 1
    other_gpu = make_gpu(db_session, gpu.server, index_on_server=1)
    rs.create_reservation(db_session, user, other_gpu, START, END, 1000, regulation, now=NOW)

    range_end = NOW + timedelta(hours=5)
    watch = ws.create_watch(db_session, user, gpu, NOW, range_end, 1000, regulation, auto_book=True)

    assert ws.attempt_auto_book(db_session, watch, gpu, regulation, now=NOW) is None
    assert rs.count_active_reservations(db_session, user.id, now=NOW) == 1
