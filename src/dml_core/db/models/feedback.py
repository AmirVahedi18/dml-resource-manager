import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dml_core.db.base import Base


class FeedbackCategory(str, enum.Enum):
    BUG = "BUG"
    PROBLEM = "PROBLEM"
    SUGGESTION = "SUGGESTION"
    OTHER = "OTHER"


class Feedback(Base):
    """A user's free-text report about the app (bug, problem, suggestion) -- admin-only to read,
    never surfaced to other students."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[FeedbackCategory] = mapped_column(
        Enum(FeedbackCategory), default=FeedbackCategory.OTHER, nullable=False
    )
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="feedback")
