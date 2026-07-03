from dataclasses import dataclass
from typing import Iterator

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from dml_bot.api.auth import InvalidInitData, TelegramWebAppUser, validate_init_data
from dml_bot.config.schema import AppConfig
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import user_service


def get_bot_token(request: Request) -> str:
    return request.app.state.bot_token


def get_admin_ids(request: Request) -> set[int]:
    return request.app.state.admin_ids


def get_app_config(request: Request) -> AppConfig:
    return request.app.state.config


def get_db_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


def get_raw_init_data(x_telegram_init_data: str = Header(default="")) -> str:
    """The raw header value, exposed so a page can re-embed it in an <img src> URL: browser
    <img> tags can't send custom headers, so the chart image endpoint is the one place initData
    travels as a query param instead -- validated identically either way, see get_telegram_user."""
    return x_telegram_init_data


def get_telegram_user(
    x_telegram_init_data: str = Header(default=""),
    init_data: str = Query(default=""),
    bot_token: str = Depends(get_bot_token),
) -> TelegramWebAppUser:
    raw = x_telegram_init_data or init_data
    try:
        return validate_init_data(raw, bot_token)
    except InvalidInitData as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def get_current_user(
    telegram_user: TelegramWebAppUser = Depends(get_telegram_user),
    session: Session = Depends(get_db_session),
) -> User:
    user = user_service.get_user_by_telegram_id(session, telegram_user.id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="not registered")
    return user


def require_admin(
    telegram_user: TelegramWebAppUser = Depends(get_telegram_user),
    admin_ids: set[int] = Depends(get_admin_ids),
) -> TelegramWebAppUser:
    if telegram_user.id not in admin_ids:
        raise HTTPException(status_code=403, detail="admins only")
    return telegram_user


@dataclass
class ViewerContext:
    telegram_user: TelegramWebAppUser
    db_user: User | None
    is_admin: bool


def get_viewer(
    telegram_user: TelegramWebAppUser = Depends(get_telegram_user),
    session: Session = Depends(get_db_session),
    admin_ids: set[int] = Depends(get_admin_ids),
) -> ViewerContext:
    db_user = user_service.get_user_by_telegram_id(session, telegram_user.id)
    if db_user is not None and not db_user.is_active:
        db_user = None
    return ViewerContext(telegram_user=telegram_user, db_user=db_user, is_admin=telegram_user.id in admin_ids)
