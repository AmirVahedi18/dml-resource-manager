import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dml_core.db.base import Base


class ReservationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    # The reservation's GPU or server was deactivated while this reservation was still upcoming
    # or in progress -- paused rather than cancelled, and rescheduled (start pushed to 1h after
    # reactivation, same original duration) the moment the GPU/server is reactivated. See
    # reservation_service.suspend_active_reservations_for_gpu/resume_suspended_reservations_for_gpu.
    SUSPENDED = "SUSPENDED"


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    gpu_id: Mapped[int] = mapped_column(ForeignKey("gpus.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ram_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    # What the GPU time is for (project/paper/experiment name) -- required at booking time, but
    # admin-only to read: never exposed on the student-facing ReservationOut schema, only on
    # AdminReservationOut (see routers/reservations.py vs routers/admin_reservations.py).
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.ACTIVE, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="reservations")
    gpu: Mapped["GPU"] = relationship(back_populates="reservations")
