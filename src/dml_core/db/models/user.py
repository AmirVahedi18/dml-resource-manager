from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dml_core.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Local username/password login, managed entirely by dml_web/services/auth_service.py.
    username: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    max_concurrent_gpus: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Promotable admin role granted by a bootstrap admin (see `WEB_ADMIN_USERNAME` in `.env`),
    # letting a TA get admin rights without redeploying. Bootstrap admins are always admins
    # regardless of this flag; see `auth_service.ensure_admin_seeded`.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")
    watches: Mapped[list["WatchSubscription"]] = relationship(back_populates="user")
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="user")
