from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from dml_core.db.models.user import User
from dml_core.services import auth_service
from dml_web import security
from dml_web.deps import get_current_user, get_session
from dml_web.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UserOut

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = auth_service.authenticate(session, payload.username, payload.password)
    return TokenResponse(access_token=security.create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        is_admin=current_user.is_admin,
        is_bootstrap=auth_service.is_bootstrap_admin(current_user.username),
        max_concurrent_gpus=current_user.max_concurrent_gpus,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    # Re-verifies the old password (rather than trusting the valid JWT alone) so a hijacked/left-
    # open session can't be used to lock the real owner out by changing the password blind.
    auth_service.authenticate(session, current_user.username, payload.old_password)
    auth_service.set_password(session, current_user, payload.new_password)
