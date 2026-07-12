from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from dml_core.db.models.feedback import Feedback, FeedbackCategory
from dml_core.db.models.user import User
from dml_core.services import feedback_service
from dml_web.deps import get_session, require_admin
from dml_web.schemas.admin_feedback import AdminFeedbackListOut, AdminFeedbackOut

router = APIRouter()


def _to_admin_out(f: Feedback) -> AdminFeedbackOut:
    return AdminFeedbackOut(
        id=f.id,
        user_id=f.user_id,
        user_full_name=f.user.full_name,
        category=f.category,
        message=f.message,
        created_at=f.created_at,
    )


@router.get("", response_model=AdminFeedbackListOut)
def list_feedback(
    user_id: int | None = None,
    category: FeedbackCategory | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> AdminFeedbackListOut:
    total = feedback_service.count_all_feedback(session, user_id=user_id, category=category)
    items = feedback_service.list_all_feedback(
        session, user_id=user_id, category=category, limit=page_size, offset=(page - 1) * page_size
    )
    return AdminFeedbackListOut(
        items=[_to_admin_out(f) for f in items], total=total, page=page, page_size=page_size
    )


@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback(
    feedback_id: int, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> None:
    feedback = session.get(Feedback, feedback_id)
    if feedback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feedback not found")
    feedback_service.delete_feedback(session, feedback)
