from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from dml_bot.db.base import Base

SINGLETON_ID = 1


class ChartSettings(Base):
    """Single global row (id is always SINGLETON_ID) holding which renderer draws the RAM-
    occupancy chart (Reserve GPU's pre-date-picker chart, View Schedule, Watches' pre-date-picker
    chart) -- a display preference, not a scheduling limit, so it's kept separate from
    `Regulation`. Seeded from `schedule_chart.default_renderer` on first run; admins can then
    change it live via the bot (see `chart_settings_service`)."""

    __tablename__ = "chart_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    renderer: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
