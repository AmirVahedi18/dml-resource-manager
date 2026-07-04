from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from dml_bot.db.base import Base


class InviteCode(Base):
    """A one-time code an admin generates for a specific (pre-filled) student registration.
    `server_ids` is a comma-separated list of `Server.id` values (empty string for interfaces
    that don't restrict server access) since there's no per-user row to attach a many-to-many
    table to until the invite is redeemed and the `User` actually exists."""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    server_ids: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
