from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from dml_core.db.models.feedback import Feedback
from dml_core.db.models.user import User
from dml_core.services import feedback_service
from dml_web.deps import get_current_user, get_session
from dml_web.schemas.feedback import FeedbackCreate, FeedbackOut

router = APIRouter()


@router.get("", response_model=list[FeedbackOut])
def list_my_feedback(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> list[Feedback]:
    return feedback_service.list_feedback_for_user(session, user.id)


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: FeedbackCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Feedback:
    return feedback_service.create_feedback(session, user, payload.category, payload.message)
