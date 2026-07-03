from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from dml_bot.api.deps import get_db_session, require_admin
from dml_bot.api.templating import templates
from dml_bot.db.models.user import User
from dml_bot.services import user_service

router = APIRouter(prefix="/api/admin/users")


def _render_list(request: Request, session: Session):
    users = user_service.list_users(session, active_only=False)
    return templates.TemplateResponse(request, "partials/admin_users_list.html", {"users": users})


@router.get("")
async def list_users(request: Request, session: Session = Depends(get_db_session), _admin=Depends(require_admin)):
    return _render_list(request, session)


@router.post("/{user_id}/toggle-active")
async def toggle_active(
    user_id: int, request: Request, session: Session = Depends(get_db_session), _admin=Depends(require_admin)
):
    user = session.get(User, user_id)
    user_service.set_active(session, user, not user.is_active)
    return _render_list(request, session)


@router.post("/{user_id}/toggle-privilege")
async def toggle_privilege(
    user_id: int, request: Request, session: Session = Depends(get_db_session), _admin=Depends(require_admin)
):
    user = session.get(User, user_id)
    user_service.set_privilege(session, user, not user.can_use_multiple_gpus)
    return _render_list(request, session)


@router.get("/new")
async def new_form(request: Request, _admin=Depends(require_admin)):
    return templates.TemplateResponse(request, "partials/admin_users_new.html", {})


@router.post("/new")
async def create(
    request: Request,
    telegram_id: int = Form(...),
    full_name: str = Form(...),
    session: Session = Depends(get_db_session),
    _admin=Depends(require_admin),
):
    try:
        user_service.register_user(session, telegram_id=telegram_id, full_name=full_name)
    except user_service.UserAlreadyExistsError as exc:
        return templates.TemplateResponse(request, "partials/admin_users_new.html", {"error": str(exc)})
    return _render_list(request, session)
