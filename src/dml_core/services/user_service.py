from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dml_core.db.models.server_access import ServerAccess
from dml_core.db.models.user import User
from dml_core.db.models.watch import WatchSubscription


class UserAlreadyExistsError(Exception):
    pass


def get_user_by_username(session: Session, username: str) -> User | None:
    return session.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()


def list_users(session: Session, active_only: bool = True) -> list[User]:
    stmt = select(User)
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def set_active(session: Session, user: User, is_active: bool) -> User:
    user.is_active = is_active
    session.flush()
    return user


def set_max_concurrent_gpus(session: Session, user: User, max_concurrent_gpus: int) -> User:
    if max_concurrent_gpus < 1:
        raise ValueError("max_concurrent_gpus must be at least 1")
    user.max_concurrent_gpus = max_concurrent_gpus
    session.flush()
    return user


def set_admin(session: Session, user: User, is_admin: bool) -> User:
    user.is_admin = is_admin
    session.flush()
    return user


def rename_user(session: Session, user: User, full_name: str) -> User:
    user.full_name = full_name
    session.flush()
    return user


def delete_user(session: Session, user: User) -> None:
    """Removes the user's account (login credentials, admin role, watches, server access) but
    keeps the `User` row and every reservation they ever made -- reservation history must never
    be lost, and `Reservation.user_id` is a required FK that report code dereferences directly
    (e.g. `r.user.full_name`), so the row can't be hard-deleted without breaking that.
    `username` is nullable specifically so it can be cleared here, freeing it up for reuse while
    the scrubbed account stays visible (inactive, credential-less) in past reservation records."""
    session.execute(delete(WatchSubscription).where(WatchSubscription.user_id == user.id))
    session.execute(delete(ServerAccess).where(ServerAccess.user_id == user.id))
    user.username = None
    user.password_hash = None
    user.is_active = False
    user.is_admin = False
    session.flush()
