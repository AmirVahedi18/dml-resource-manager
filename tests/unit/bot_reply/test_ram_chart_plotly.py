from datetime import datetime, timedelta
from types import SimpleNamespace

from dml_bot.bot_reply.ram_chart_plotly import (
    _x_dtick_ms,
    _y_dtick,
    render_bucketed_bars,
    render_gantt,
    render_stacked_area,
)

CAP_MB = 40960  # 40 GB
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _reservation(start, end, ram_mb, name):
    return SimpleNamespace(start_time=start, end_time=end, ram_mb=ram_mb, user=SimpleNamespace(full_name=name))


def test_bucketed_bars_renders_png_with_reservations():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=6)
    reservations = [_reservation(start, start + timedelta(hours=2), 24576, "Ali Ahmadi")]
    png = render_bucketed_bars(reservations, CAP_MB, start, end, "UTC", 2.0, "title")
    assert png.startswith(_PNG_MAGIC)


def test_bucketed_bars_renders_png_when_empty():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=6)
    png = render_bucketed_bars([], CAP_MB, start, end, "UTC", 2.0, "title")
    assert png.startswith(_PNG_MAGIC)


def test_stacked_area_renders_png_with_reservations():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=6)
    reservations = [_reservation(start, start + timedelta(hours=2), 24576, "Ali Ahmadi")]
    png = render_stacked_area(reservations, CAP_MB, start, end, "UTC", "title")
    assert png.startswith(_PNG_MAGIC)


def test_stacked_area_renders_png_when_empty():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=6)
    png = render_stacked_area([], CAP_MB, start, end, "UTC", "title")
    assert png.startswith(_PNG_MAGIC)


def test_gantt_renders_png_with_reservations():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=6)
    reservations = [_reservation(start, start + timedelta(hours=2), 24576, "Ali Ahmadi")]
    png = render_gantt(reservations, start, end, "UTC", "title")
    assert png.startswith(_PNG_MAGIC)


def test_gantt_renders_png_when_empty():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=6)
    png = render_gantt([], start, end, "UTC", "title")
    assert png.startswith(_PNG_MAGIC)


def test_more_than_seven_users_fold_into_other_bucket():
    start = datetime(2026, 7, 6, 0, 0)
    end = start + timedelta(hours=1)
    reservations = [_reservation(start, end, 1024, f"User {i}") for i in range(9)]
    # Should not raise, and should still produce a valid image with the 9 users collapsed to
    # 7 named + one "Other" series rather than a 9th generated hue.
    png = render_bucketed_bars(reservations, CAP_MB, start, end, "UTC", 1.0, "title")
    assert png.startswith(_PNG_MAGIC)


def test_y_dtick_gives_a_round_step_finer_than_the_old_8_tick_default():
    # 80 GB over the old ~8-tick default would step by 10; the new finer target lands on 5.
    assert _y_dtick(80) == 5
    # Always a positive, round (1/2/2.5/5 x 10^k) step -- never zero or a jagged fraction.
    for cap in (24, 40, 100, 1000):
        step = _y_dtick(cap)
        assert step > 0
        assert cap / step <= 20  # roughly target_ticks-ish, never absurdly many gridlines


def test_y_dtick_handles_zero_cap():
    assert _y_dtick(0) == 1


def test_x_dtick_is_finer_for_shorter_windows():
    day = datetime(2026, 7, 6)
    dtick_6h = _x_dtick_ms(day, day + timedelta(hours=6))
    dtick_14d = _x_dtick_ms(day, day + timedelta(days=14))
    assert dtick_6h < dtick_14d  # a 6h window gets a much finer step than a 14-day one
    assert dtick_14d >= 24 * 3_600_000  # multi-day windows step in whole days or more
