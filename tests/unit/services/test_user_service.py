import pytest

from dml_bot.services import user_service as us


def test_register_and_lookup(db_session):
    user = us.register_user(db_session, telegram_id=42, full_name="Alice")
    found = us.get_user_by_telegram_id(db_session, 42)
    assert found.id == user.id


def test_register_duplicate_telegram_id_raises(db_session):
    us.register_user(db_session, telegram_id=42, full_name="Alice")
    with pytest.raises(us.UserAlreadyExistsError):
        us.register_user(db_session, telegram_id=42, full_name="Alice Again")


def test_lookup_unknown_returns_none(db_session):
    assert us.get_user_by_telegram_id(db_session, 999) is None


def test_list_users_excludes_inactive_by_default(db_session):
    active = us.register_user(db_session, telegram_id=1, full_name="Active")
    inactive = us.register_user(db_session, telegram_id=2, full_name="Inactive")
    us.set_active(db_session, inactive, False)

    listed = us.list_users(db_session)
    assert [u.id for u in listed] == [active.id]


def test_set_privilege(db_session):
    user = us.register_user(db_session, telegram_id=1, full_name="Alice")
    us.set_privilege(db_session, user, True)
    assert user.can_use_multiple_gpus is True
