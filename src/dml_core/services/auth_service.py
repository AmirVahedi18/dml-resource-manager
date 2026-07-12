"""Local username/password credential management for the web interface. Framework-agnostic (only
SQLAlchemy + bcrypt), following the same pattern as the other services/*.py modules."""
import os

import bcrypt
from sqlalchemy.orm import Session

from dml_core.db.models.user import User
from dml_core.services import user_service


def is_bootstrap_admin(username: str | None) -> bool:
    """True for the account seeded from WEB_ADMIN_USERNAME -- the guaranteed recovery admin,
    which must stay deletable/deactivatable/de-admin-able by no one (not even itself), since
    there'd otherwise be no way back in if every other admin were locked out."""
    bootstrap_username = os.environ.get("WEB_ADMIN_USERNAME", "").strip()
    return bool(bootstrap_username) and username == bootstrap_username


class UsernameAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user_with_credentials(
    session: Session,
    username: str,
    password: str,
    full_name: str,
    max_concurrent_gpus: int = 1,
) -> User:
    username = username.strip()
    if user_service.get_user_by_username(session, username) is not None:
        raise UsernameAlreadyExistsError(f"The username '{username}' is already taken.")
    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name,
        max_concurrent_gpus=max_concurrent_gpus,
    )
    session.add(user)
    session.flush()
    return user


def authenticate(session: Session, username: str, password: str) -> User:
    """Raises InvalidCredentialsError for an unknown username, a deactivated account, or a wrong
    password -- deliberately not distinguishing which, so a login form can't be used to enumerate
    valid usernames."""
    user = user_service.get_user_by_username(session, username.strip())
    if user is None or not user.is_active or not user.password_hash:
        raise InvalidCredentialsError("invalid username or password")
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("invalid username or password")
    return user


def set_password(session: Session, user: User, new_password: str) -> User:
    user.password_hash = hash_password(new_password)
    session.flush()
    return user


def ensure_admin_seeded(session: Session, username: str, password: str) -> User | None:
    """Idempotently creates the bootstrap web admin from WEB_ADMIN_USERNAME/WEB_ADMIN_PASSWORD.
    Does nothing if an account with that username already exists (won't reset its password on
    every restart); returns None in that case so the caller can decide whether to log anything."""
    if not username or not password:
        return None
    existing = user_service.get_user_by_username(session, username.strip())
    if existing is not None:
        return None
    user = create_user_with_credentials(session, username=username, password=password, full_name=username)
    user_service.set_admin(session, user, True)
    return user
