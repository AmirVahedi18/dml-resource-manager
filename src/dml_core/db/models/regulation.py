from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from dml_core.db.base import Base

SINGLETON_ID = 1


class Regulation(Base):
    """Single global row (id is always SINGLETON_ID) holding the lab's active reservation limits."""

    __tablename__ = "regulation"

    id: Mapped[int] = mapped_column(primary_key=True)
    max_ram_per_reservation_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    max_duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    booking_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    min_reservation_slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    max_active_reservations_per_user: Mapped[int] = mapped_column(Integer, nullable=False)
    min_cancellation_notice_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
