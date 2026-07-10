from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dml_core.db.base import Base


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Set instead of physically deleting the row, so historical reservations on this server's
    # GPUs keep resolving `reservation.gpu.server` instead of hitting a dangling FK.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    gpus: Mapped[list["GPU"]] = relationship(back_populates="server")
