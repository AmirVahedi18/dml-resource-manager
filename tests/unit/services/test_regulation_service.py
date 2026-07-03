import pytest

from dml_bot.config.schema import RegulationConfig
from dml_bot.services import regulation_service as regs


def test_ensure_seeded_creates_singleton(db_session):
    seed = RegulationConfig(max_ram_per_reservation_mb=8192)
    regulation = regs.ensure_seeded(db_session, seed)
    assert regulation.max_ram_per_reservation_mb == 8192


def test_ensure_seeded_is_idempotent(db_session):
    seed = RegulationConfig(max_ram_per_reservation_mb=8192)
    first = regs.ensure_seeded(db_session, seed)
    second = regs.ensure_seeded(db_session, RegulationConfig(max_ram_per_reservation_mb=1))
    assert second.id == first.id
    assert second.max_ram_per_reservation_mb == 8192


def test_update_regulation(db_session):
    regs.ensure_seeded(db_session, RegulationConfig())
    updated = regs.update_regulation(db_session, updated_by=555, max_duration_hours=24)
    assert updated.max_duration_hours == 24
    assert updated.updated_by == 555


def test_update_unknown_field_raises(db_session):
    regs.ensure_seeded(db_session, RegulationConfig())
    with pytest.raises(ValueError):
        regs.update_regulation(db_session, updated_by=555, not_a_field=1)
