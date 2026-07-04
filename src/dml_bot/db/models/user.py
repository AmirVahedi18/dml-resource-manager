from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dml_bot.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    student_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    can_use_multiple_gpus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Promotable admin role granted by a bootstrap admin (see `ADMIN_IDS` in `.env`), letting a TA
    # get admin rights without redeploying. Bootstrap admins are always admins regardless of this
    # flag; see `dml_bot.bot.auth.is_admin`.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")
    watches: Mapped[list["WatchSubscription"]] = relationship(back_populates="user")
