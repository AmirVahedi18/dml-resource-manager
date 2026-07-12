from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dml_core.db.base import Base


class WatchSubscription(Base):
    """A student's request to be notified when a time range frees up on a GPU."""

    __tablename__ = "watch_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    gpu_id: Mapped[int] = mapped_column(ForeignKey("gpus.id"), nullable=False)
    range_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    range_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    min_ram_needed_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    # Required (mirrors Reservation.description), carried over onto the reservation created by
    # attempt_auto_book so the description a student gave when watching survives into the
    # eventual booking. Admin-only to read, same as Reservation.description.
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    # Opt-in: instead of just notifying, automatically book the freed window (from whenever it
    # frees through `range_end`, capped by the regulation's max duration) the instant a match is
    # found. Falls back to a plain notification if the auto-book attempt is rejected by any
    # reservation rule (e.g. the student is already at their active-reservation limit).
    auto_book: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="watches")
    gpu: Mapped["GPU"] = relationship(back_populates="watches")
