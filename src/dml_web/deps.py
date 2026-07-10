"""FastAPI dependencies: a DB session per request, and the current-user/admin-only guards every
protected route depends on."""
from typing import Iterator

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from dml_core.config.schema import AppConfig
from dml_core.db.models.user import User
from dml_core.db.session import session_scope
from dml_web import security

_bearer_scheme = HTTPBearer(auto_error=False)


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        user_id = security.decode_user_id(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


def get_app_cfg(request: Request) -> AppConfig:
    return request.app.state.app_cfg
