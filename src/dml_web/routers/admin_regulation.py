from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dml_bot.db.models.user import User
from dml_bot.db.models.regulation import Regulation
from dml_bot.services import regulation_service
from dml_web.deps import get_session, require_admin
from dml_web.schemas.admin_regulation import RegulationUpdateRequest
from dml_web.schemas.schedule import RegulationOut

router = APIRouter()


@router.get("", response_model=RegulationOut)
def get_regulation(
    session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> Regulation:
    return regulation_service.get_regulation(session)


@router.put("", response_model=RegulationOut)
def update_regulation(
    payload: RegulationUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> Regulation:
    return regulation_service.update_regulation(session, updated_by=current_user.id, **payload.model_dump())
