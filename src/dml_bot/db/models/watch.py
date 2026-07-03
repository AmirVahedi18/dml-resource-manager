from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dml_bot.db.base import Base


class WatchSubscription(Base):
    """A student's request to be notified when a time range frees up on a GPU."""

    __tablename__ = "watch_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    gpu_id: Mapped[int] = mapped_column(ForeignKey("gpus.id"), nullable=False)
    range_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    range_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    min_ram_needed_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="watches")
    gpu: Mapped["GPU"] = relationship(back_populates="watches")
