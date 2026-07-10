from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dml_core.db.models.user import User
from dml_core.services import auth_service, server_access_service, user_service
from dml_web.deps import get_session, require_admin
from dml_web.schemas.admin_users import (
    BulkUserCreateRequest,
    BulkUserCreateResponse,
    BulkUserCreateResultItem,
    RenameUserRequest,
    ResetPasswordRequest,
    SetActiveRequest,
    SetAdminRequest,
    SetMaxConcurrentGpusRequest,
    SetServerAccessRequest,
    UserAdminOut,
)

router = APIRouter()


def _to_admin_out(session: Session, user: User) -> UserAdminOut:
    server_ids = sorted(server_access_service.list_accessible_server_ids(session, user.id))
    return UserAdminOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        max_concurrent_gpus=user.max_concurrent_gpus,
        server_ids=server_ids,
    )


def _get_user_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.get("", response_model=list[UserAdminOut])
def list_users(
    session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> list[UserAdminOut]:
    return [_to_admin_out(session, u) for u in user_service.list_users(session, active_only=False)]


@router.post("/bulk", response_model=BulkUserCreateResponse)
def bulk_create_users(
    payload: BulkUserCreateRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> BulkUserCreateResponse:
    """Best-effort per-row creation (not all-or-nothing) -- a typo or duplicate username in one row
    of a large pasted batch shouldn't block every other, valid row from being created.
    `create_user_with_credentials` checks for a duplicate username *before* adding/flushing
    anything, so a rejected row never touches the session -- no rollback needed to keep earlier
    successful rows in this same batch intact."""
    results: list[BulkUserCreateResultItem] = []
    for item in payload.users:
        try:
            user = auth_service.create_user_with_credentials(
                session,
                username=item.username,
                password=item.password,
                full_name=item.full_name,
                max_concurrent_gpus=item.max_concurrent_gpus,
            )
            if item.server_ids:
                server_access_service.set_access(session, user.id, set(item.server_ids))
            results.append(BulkUserCreateResultItem(username=item.username, success=True, user_id=user.id))
        except auth_service.UsernameAlreadyExistsError as exc:
            results.append(BulkUserCreateResultItem(username=item.username, success=False, error=str(exc)))
    return BulkUserCreateResponse(results=results)


@router.patch("/{user_id}/rename", response_model=UserAdminOut)
def rename_user(
    user_id: int,
    payload: RenameUserRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> UserAdminOut:
    user = _get_user_or_404(session, user_id)
    user_service.rename_user(session, user, payload.full_name)
    return _to_admin_out(session, user)


@router.patch("/{user_id}/active", response_model=UserAdminOut)
def set_active(
    user_id: int,
    payload: SetActiveRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> UserAdminOut:
    user = _get_user_or_404(session, user_id)
    if not payload.is_active and auth_service.is_bootstrap_admin(user.username):
        raise HTTPException(422, "Cannot deactivate the bootstrap admin account")
    user_service.set_active(session, user, payload.is_active)
    return _to_admin_out(session, user)


@router.patch("/{user_id}/admin", response_model=UserAdminOut)
def set_admin(
    user_id: int,
    payload: SetAdminRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> UserAdminOut:
    user = _get_user_or_404(session, user_id)
    if user.is_admin and not payload.is_admin:
        if auth_service.is_bootstrap_admin(user.username):
            raise HTTPException(422, "Cannot revoke the bootstrap admin account's admin role")
        remaining_admins = [u for u in user_service.list_users(session, active_only=True) if u.is_admin]
        if len(remaining_admins) <= 1:
            raise HTTPException(422, "Cannot revoke the last remaining admin")
    user_service.set_admin(session, user, payload.is_admin)
    return _to_admin_out(session, user)


@router.patch("/{user_id}/max-concurrent-gpus", response_model=UserAdminOut)
def set_max_concurrent_gpus(
    user_id: int,
    payload: SetMaxConcurrentGpusRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> UserAdminOut:
    user = _get_user_or_404(session, user_id)
    user_service.set_max_concurrent_gpus(session, user, payload.max_concurrent_gpus)
    return _to_admin_out(session, user)


@router.patch("/{user_id}/server-access", response_model=UserAdminOut)
def set_server_access(
    user_id: int,
    payload: SetServerAccessRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> UserAdminOut:
    user = _get_user_or_404(session, user_id)
    server_access_service.set_access(session, user.id, set(payload.server_ids))
    return _to_admin_out(session, user)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> None:
    user = _get_user_or_404(session, user_id)
    auth_service.set_password(session, user, payload.new_password)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> None:
    user = _get_user_or_404(session, user_id)
    if auth_service.is_bootstrap_admin(user.username):
        raise HTTPException(422, "Cannot delete the bootstrap admin account")
    user_service.delete_user(session, user)
