from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dml_bot.db.models.server import Server
from dml_bot.db.models.server_access import ServerAccess


def list_accessible_server_ids(session: Session, user_id: int) -> set[int]:
    stmt = select(ServerAccess.server_id).where(ServerAccess.user_id == user_id)
    return set(session.execute(stmt).scalars().all())


def list_accessible_servers(session: Session, user_id: int) -> list[Server]:
    stmt = select(Server).join(ServerAccess, ServerAccess.server_id == Server.id).where(
        ServerAccess.user_id == user_id
    )
    return list(session.execute(stmt).scalars().all())


def set_access(session: Session, user_id: int, server_ids: set[int]) -> None:
    """Replaces the user's full set of accessible servers with `server_ids`."""
    session.execute(delete(ServerAccess).where(ServerAccess.user_id == user_id))
    for server_id in server_ids:
        session.add(ServerAccess(user_id=user_id, server_id=server_id))
    session.flush()


def delete_access_for_user(session: Session, user_id: int) -> None:
    session.execute(delete(ServerAccess).where(ServerAccess.user_id == user_id))


def delete_access_for_server(session: Session, server_id: int) -> None:
    session.execute(delete(ServerAccess).where(ServerAccess.server_id == server_id))
