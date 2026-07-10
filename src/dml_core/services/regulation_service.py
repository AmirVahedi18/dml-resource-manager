from datetime import datetime, timezone

from sqlalchemy.orm import Session

from dml_core.config.schema import RegulationConfig
from dml_core.db.models.regulation import SINGLETON_ID, Regulation


def ensure_seeded(session: Session, seed: RegulationConfig) -> Regulation:
    regulation = session.get(Regulation, SINGLETON_ID)
    if regulation is not None:
        return regulation

    regulation = Regulation(
        id=SINGLETON_ID,
        max_ram_per_reservation_gb=seed.max_ram_per_reservation_gb,
        max_duration_hours=seed.max_duration_hours,
        booking_horizon_days=seed.booking_horizon_days,
        min_reservation_slot_minutes=seed.min_reservation_slot_minutes,
        max_active_reservations_per_user=seed.max_active_reservations_per_user,
        min_cancellation_notice_minutes=seed.min_cancellation_notice_minutes,
    )
    session.add(regulation)
    session.flush()
    return regulation


def get_regulation(session: Session) -> Regulation:
    regulation = session.get(Regulation, SINGLETON_ID)
    if regulation is None:
        raise RuntimeError("Regulation not seeded; call ensure_seeded() at startup")
    return regulation


def update_regulation(session: Session, updated_by: int, **fields: int) -> Regulation:
    regulation = get_regulation(session)
    for key, value in fields.items():
        if not hasattr(regulation, key):
            raise ValueError(f"Unknown regulation field: {key}")
        setattr(regulation, key, value)
    regulation.updated_by = updated_by
    regulation.updated_at = datetime.now(timezone.utc)
    session.flush()
    return regulation
