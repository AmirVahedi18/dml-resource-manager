from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from dml_core.db.models.feedback import Feedback, FeedbackCategory
from dml_core.db.models.user import User


def create_feedback(
    session: Session, user: User, category: FeedbackCategory, message: str
) -> Feedback:
    feedback = Feedback(user_id=user.id, category=category, message=message)
    session.add(feedback)
    session.flush()
    return feedback


def list_feedback_for_user(session: Session, user_id: int) -> list[Feedback]:
    stmt = (
        select(Feedback)
        .where(Feedback.user_id == user_id)
        .order_by(Feedback.created_at.desc())
    )
    return list(session.execute(stmt).scalars().all())


def _feedback_filter_stmt(user_id: int | None, category: FeedbackCategory | None):
    stmt = select(Feedback)
    if user_id is not None:
        stmt = stmt.where(Feedback.user_id == user_id)
    if category is not None:
        stmt = stmt.where(Feedback.category == category)
    return stmt


def list_all_feedback(
    session: Session,
    *,
    user_id: int | None = None,
    category: FeedbackCategory | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[Feedback]:
    stmt = (
        _feedback_filter_stmt(user_id, category)
        .options(joinedload(Feedback.user))
        .order_by(Feedback.created_at.desc())
    )
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).unique().scalars().all())


def count_all_feedback(
    session: Session, *, user_id: int | None = None, category: FeedbackCategory | None = None
) -> int:
    stmt = _feedback_filter_stmt(user_id, category)
    return session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()


def delete_feedback(session: Session, feedback: Feedback) -> None:
    session.delete(feedback)
    session.flush()
