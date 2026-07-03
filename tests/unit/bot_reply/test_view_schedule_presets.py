from types import SimpleNamespace

from dml_bot.bot_reply.handlers.student.view_schedule import _range_label, _range_presets


def _config(range_days_options):
    return SimpleNamespace(schedule_chart=SimpleNamespace(range_days_options=range_days_options))


def test_today_is_always_present_and_first():
    presets = _range_presets(_config([3, 5, 7, 10, 14]), booking_horizon_days=90)
    assert presets[0] == ("Today", 0)


def test_options_longer_than_horizon_are_hidden():
    presets = _range_presets(_config([3, 5, 7, 10, 14]), booking_horizon_days=5)
    days = [d for _, d in presets]
    assert days == [0, 3, 5]  # 7, 10, 14 exceed the 5-day horizon and are hidden


def test_all_options_shown_when_horizon_is_generous():
    presets = _range_presets(_config([3, 5, 7, 10, 14]), booking_horizon_days=90)
    days = [d for _, d in presets]
    assert days == [0, 3, 5, 7, 10, 14]


def test_range_label_today_vs_days():
    assert _range_label(0) == "today"
    assert _range_label(7) == "the next 7 days"
