from datetime import datetime, timedelta, timezone

from dml_bot.utils import time_utils as tu


def test_is_slot_aligned():
    assert tu.is_slot_aligned(datetime(2026, 7, 1, 8, 30), 30)
    assert not tu.is_slot_aligned(datetime(2026, 7, 1, 8, 31), 30)


def test_floor_to_slot_rounds_up():
    dt = datetime(2026, 7, 1, 8, 5)
    assert tu.floor_to_slot(dt, 30) == datetime(2026, 7, 1, 8, 30)


def test_floor_to_slot_already_aligned_is_noop():
    dt = datetime(2026, 7, 1, 8, 30)
    assert tu.floor_to_slot(dt, 30) == dt


def test_align_down_to_slot_rounds_down():
    dt = datetime(2026, 7, 1, 8, 55)
    assert tu.align_down_to_slot(dt, 30) == datetime(2026, 7, 1, 8, 30)


def test_align_down_to_slot_already_aligned_is_noop():
    dt = datetime(2026, 7, 1, 8, 30)
    assert tu.align_down_to_slot(dt, 30) == dt


def test_generate_slot_starts_respects_not_before():
    range_start = datetime(2026, 7, 1, 0, 0)
    range_end = datetime(2026, 7, 1, 2, 0)
    not_before = datetime(2026, 7, 1, 0, 45)
    slots = tu.generate_slot_starts(range_start, range_end, 30, not_before)
    assert slots == [datetime(2026, 7, 1, 1, 0), datetime(2026, 7, 1, 1, 30)]


def test_local_day_range_utc_for_tehran():
    start, end = tu.local_day_range_utc(datetime(2026, 7, 1).date(), "Asia/Tehran")
    assert end - start == timedelta(days=1)
    assert start.hour == 20 and start.minute == 30  # 00:00 +03:30 on 2026-07-01 is 2026-06-30 20:30 UTC


def test_to_naive_utc_idempotent_on_naive_input():
    dt = datetime(2026, 7, 1, 8, 0)
    assert tu.to_naive_utc(dt) == dt


def test_to_local_label_round_trips():
    utc_dt = datetime(2026, 7, 1, 12, 0)
    label = tu.to_local_label(utc_dt, "UTC")
    assert label == "12:00"
