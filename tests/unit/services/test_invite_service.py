import pytest

from dml_bot.services import invite_service as inv
from dml_bot.services import server_access_service, user_service


def test_create_invite_generates_unique_code(db_session):
    invite = inv.create_invite(db_session, full_name="Alice")
    assert len(invite.code) == 8
    assert not invite.is_used
    assert inv.get_invite_by_code(db_session, invite.code) is not None


def test_redeem_invite_registers_user_and_grants_access(db_session):
    server_id = 7
    invite = inv.create_invite(db_session, full_name="Alice", server_ids={server_id})

    user = inv.redeem_invite(db_session, code=invite.code, telegram_id=1234)

    assert user.full_name == "Alice"
    assert user_service.get_user_by_telegram_id(db_session, 1234).id == user.id
    assert server_access_service.list_accessible_server_ids(db_session, user.id) == {server_id}
    assert invite.is_used
    assert invite.used_at is not None


def test_redeem_invite_is_case_insensitive_and_trims_whitespace(db_session):
    invite = inv.create_invite(db_session, full_name="Alice")
    user = inv.redeem_invite(db_session, code=f"  {invite.code.lower()}  ", telegram_id=1234)
    assert user.full_name == "Alice"


def test_redeem_unknown_code_raises(db_session):
    with pytest.raises(inv.InviteNotFoundError):
        inv.redeem_invite(db_session, code="NOSUCH01", telegram_id=1234)


def test_redeem_used_code_raises_and_does_not_create_second_user(db_session):
    invite = inv.create_invite(db_session, full_name="Alice")
    inv.redeem_invite(db_session, code=invite.code, telegram_id=1234)

    with pytest.raises(inv.InviteAlreadyUsedError):
        inv.redeem_invite(db_session, code=invite.code, telegram_id=5678)
    assert user_service.get_user_by_telegram_id(db_session, 5678) is None


def test_redeem_invite_for_already_registered_telegram_id_raises_and_leaves_invite_unused(db_session):
    user_service.register_user(db_session, telegram_id=1234, full_name="Existing")
    invite = inv.create_invite(db_session, full_name="Alice")

    with pytest.raises(user_service.UserAlreadyExistsError):
        inv.redeem_invite(db_session, code=invite.code, telegram_id=1234)
    assert not invite.is_used


def test_list_pending_invites_excludes_used(db_session):
    pending = inv.create_invite(db_session, full_name="Alice")
    redeemed = inv.create_invite(db_session, full_name="Bob")
    inv.redeem_invite(db_session, code=redeemed.code, telegram_id=999)

    listed = inv.list_pending_invites(db_session)
    assert [i.id for i in listed] == [pending.id]


def test_revoke_invite_deletes_it(db_session):
    invite = inv.create_invite(db_session, full_name="Alice")
    inv.revoke_invite(db_session, invite)
    assert inv.get_invite_by_code(db_session, invite.code) is None
