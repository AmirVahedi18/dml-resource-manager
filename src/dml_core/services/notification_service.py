from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_core.db.models.notification import UserNotification
from dml_core.db.models.server_access import ServerAccess


def notify_user(session: Session, user_id: int, message: str) -> UserNotification:
    notification = UserNotification(user_id=user_id, message=message)
    session.add(notification)
    session.flush()
    return notification


def notify_server_access_users(session: Session, server_id: int, message: str) -> list[UserNotification]:
    """Queues `message` for every student with access to `server_id` -- used when a server or one
    of its GPUs is deactivated/reactivated, so only students who can actually use it are told."""
    user_ids = session.execute(
        select(ServerAccess.user_id).where(ServerAccess.server_id == server_id)
    ).scalars().all()
    return [notify_user(session, user_id, message) for user_id in user_ids]


def list_undismissed(session: Session, user_id: int) -> list[UserNotification]:
    stmt = (
        select(UserNotification)
        .where(UserNotification.user_id == user_id, UserNotification.dismissed_at.is_(None))
        .order_by(UserNotification.created_at)
    )
    return list(session.execute(stmt).scalars().all())


def dismiss(session: Session, notification: UserNotification, now: datetime | None = None) -> UserNotification:
    notification.dismissed_at = now or datetime.now(timezone.utc)
    session.flush()
    return notification
