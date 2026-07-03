from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dml_bot.db.base import Base


class GPU(Base):
    __tablename__ = "gpus"
    __table_args__ = (UniqueConstraint("server_id", "index_on_server", name="uq_gpu_server_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), nullable=False)
    index_on_server: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    total_ram_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    server: Mapped["Server"] = relationship(back_populates="gpus")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="gpu")
    watches: Mapped[list["WatchSubscription"]] = relationship(back_populates="gpu")
