"""Shared 'can this user use this server/GPU' checks for web routers -- mirrors
`bot_reply/gpu_picker.py::accessible_server_ids_for`'s rule (admins have implicit access to every
server) but kept web-local since it's routing/authorization glue, not core business logic; the bot
keeps its own copy for the same reason (see the web-interface plan's independence rationale)."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.user import User
from dml_bot.services import server_access_service


def accessible_server_ids(session: Session, user: User) -> set[int] | None:
    """None means unrestricted (admin)."""
    if user.is_admin:
        return None
    return server_access_service.list_accessible_server_ids(session, user.id)


def ensure_server_access(session: Session, user: User, server_id: int) -> None:
    accessible = accessible_server_ids(session, user)
    if accessible is not None and server_id not in accessible:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No access to this server")


def ensure_gpu_access(session: Session, user: User, gpu: GPU) -> None:
    ensure_server_access(session, user, gpu.server_id)
