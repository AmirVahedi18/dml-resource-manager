import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_bot.db.models.invite_code import InviteCode
from dml_bot.db.models.user import User
from dml_bot.services import server_access_service, user_service

# Excludes visually-ambiguous characters (0/O, 1/I) since a code is meant to be read aloud or
# retyped by a student, not copy-pasted.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 8


class InviteNotFoundError(Exception):
    pass


class InviteAlreadyUsedError(Exception):
    pass


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def get_invite_by_code(session: Session, code: str) -> InviteCode | None:
    normalized = code.strip().upper()
    return session.execute(
        select(InviteCode).where(InviteCode.code == normalized)
    ).scalar_one_or_none()


def create_invite(session: Session, full_name: str, server_ids: set[int] | None = None) -> InviteCode:
    server_ids_str = ",".join(str(i) for i in sorted(server_ids or set()))
    while True:
        code = _generate_code()
        if get_invite_by_code(session, code) is None:
            break
    invite = InviteCode(code=code, full_name=full_name, server_ids=server_ids_str)
    session.add(invite)
    session.flush()
    return invite


def list_pending_invites(session: Session) -> list[InviteCode]:
    stmt = select(InviteCode).where(InviteCode.is_used.is_(False)).order_by(InviteCode.created_at)
    return list(session.execute(stmt).scalars().all())


def revoke_invite(session: Session, invite: InviteCode) -> None:
    session.delete(invite)
    session.flush()


def redeem_invite(session: Session, code: str, telegram_id: int) -> User:
    """Creates the User pre-configured by the invite (full name + server access) and links it to
    `telegram_id`. Raises InviteNotFoundError / InviteAlreadyUsedError for a bad code, or
    user_service.UserAlreadyExistsError if `telegram_id` is already registered (e.g. a
    deactivated account) -- in that case the invite is left unused so it can still be retried."""
    invite = get_invite_by_code(session, code)
    if invite is None:
        raise InviteNotFoundError(f"no invite with code {code!r}")
    if invite.is_used:
        raise InviteAlreadyUsedError(f"invite {code!r} has already been used")

    user = user_service.register_user(session, telegram_id=telegram_id, full_name=invite.full_name)

    server_ids = {int(x) for x in invite.server_ids.split(",") if x}
    if server_ids:
        server_access_service.set_access(session, user.id, server_ids)

    invite.is_used = True
    invite.used_at = datetime.now(timezone.utc)
    session.flush()
    return user
