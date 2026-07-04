import pytest

from dml_bot.services import chart_settings_service as ccs


def test_get_renderer_defaults_to_legacy_when_unseeded(db_session):
    assert ccs.get_renderer(db_session) == "legacy"


def test_ensure_seeded_creates_singleton(db_session):
    settings = ccs.ensure_seeded(db_session, "plotly_bars")
    assert settings.renderer == "plotly_bars"
    assert ccs.get_renderer(db_session) == "plotly_bars"


def test_ensure_seeded_is_idempotent(db_session):
    ccs.ensure_seeded(db_session, "plotly_bars")
    second = ccs.ensure_seeded(db_session, "plotly_area")
    assert second.renderer == "plotly_bars"


def test_ensure_seeded_falls_back_to_legacy_for_unknown_default(db_session):
    settings = ccs.ensure_seeded(db_session, "not_a_renderer")
    assert settings.renderer == "legacy"


def test_set_renderer_updates_existing_row(db_session):
    ccs.ensure_seeded(db_session, "legacy")
    updated = ccs.set_renderer(db_session, updated_by=999, renderer="plotly_gantt")
    assert updated.renderer == "plotly_gantt"
    assert updated.updated_by == 999
    assert ccs.get_renderer(db_session) == "plotly_gantt"


def test_set_renderer_creates_row_if_missing(db_session):
    updated = ccs.set_renderer(db_session, updated_by=1, renderer="plotly_area")
    assert updated.renderer == "plotly_area"


def test_set_renderer_rejects_unknown_value(db_session):
    with pytest.raises(ValueError):
        ccs.set_renderer(db_session, updated_by=1, renderer="bogus")
