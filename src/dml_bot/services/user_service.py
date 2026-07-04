from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dml_bot.db.models.reservation import Reservation
from dml_bot.db.models.server_access import ServerAccess
from dml_bot.db.models.user import User
from dml_bot.db.models.watch import WatchSubscription


class UserAlreadyExistsError(Exception):
    pass


def register_user(
    session: Session, telegram_id: int, full_name: str, student_id: str | None = None
) -> User:
    if get_user_by_telegram_id(session, telegram_id) is not None:
        raise UserAlreadyExistsError(f"telegram_id {telegram_id} is already registered")
    user = User(telegram_id=telegram_id, full_name=full_name, student_id=student_id)
    session.add(user)
    session.flush()
    return user


def get_user_by_telegram_id(session: Session, telegram_id: int) -> User | None:
    return session.execute(
        select(User).where(User.telegram_id == telegram_id)
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


def set_privilege(session: Session, user: User, can_use_multiple_gpus: bool) -> User:
    user.can_use_multiple_gpus = can_use_multiple_gpus
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
    """Permanently deletes the user and all their reservations/watches/server-access grants.
    There's no FK cascade configured at the DB level (SQLite FK enforcement isn't enabled in this
    project), so the dependent rows are deleted explicitly here to avoid leaving orphaned rows
    behind."""
    session.execute(delete(WatchSubscription).where(WatchSubscription.user_id == user.id))
    session.execute(delete(Reservation).where(Reservation.user_id == user.id))
    session.execute(delete(ServerAccess).where(ServerAccess.user_id == user.id))
    session.delete(user)
    session.flush()
