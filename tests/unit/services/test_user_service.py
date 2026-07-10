from dml_core.services import user_service as us
from tests.factories import make_user


def test_list_users_excludes_inactive_by_default(db_session):
    active = make_user(db_session, full_name="Active")
    inactive = make_user(db_session, full_name="Inactive")
    us.set_active(db_session, inactive, False)

    listed = us.list_users(db_session)
    assert [u.id for u in listed] == [active.id]


def test_set_max_concurrent_gpus(db_session):
    user = make_user(db_session, full_name="Alice")
    assert user.max_concurrent_gpus == 1
    us.set_max_concurrent_gpus(db_session, user, 3)
    assert user.max_concurrent_gpus == 3


def test_set_admin(db_session):
    user = make_user(db_session, full_name="Alice")
    assert user.is_admin is False
    us.set_admin(db_session, user, True)
    assert user.is_admin is True
    us.set_admin(db_session, user, False)
    assert user.is_admin is False
