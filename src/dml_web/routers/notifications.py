from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dml_core.db.models.notification import UserNotification
from dml_core.db.models.user import User
from dml_core.services import notification_service
from dml_web.deps import get_current_user, get_session
from dml_web.schemas.notifications import NotificationOut

router = APIRouter()


@router.get("", response_model=list[NotificationOut])
def list_my_notifications(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> list[UserNotification]:
    return notification_service.list_undismissed(session, user.id)


@router.post("/{notification_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_notification(
    notification_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> None:
    notification = session.get(UserNotification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notification_service.dismiss(session, notification)
