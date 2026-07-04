from types import SimpleNamespace

from dml_bot.bot import auth
from dml_bot.services import user_service


def _context(admin_ids):
    return SimpleNamespace(bot_data={"admin_ids": set(admin_ids)})


def test_bootstrap_admin_is_admin_without_a_user_record(db_session):
    context = _context({999})
    assert auth.is_bootstrap_admin(999, context) is True
    assert auth.is_admin(db_session, 999, context) is True


def test_unregistered_non_bootstrap_user_is_not_admin(db_session):
    context = _context({999})
    assert auth.is_admin(db_session, 555, context) is False


def test_db_promoted_user_is_admin(db_session):
    context = _context({999})
    user = user_service.register_user(db_session, telegram_id=555, full_name="TA")
    user_service.set_admin(db_session, user, True)

    assert auth.is_bootstrap_admin(555, context) is False
    assert auth.is_admin(db_session, 555, context) is True


def test_deactivated_promoted_user_is_not_admin(db_session):
    context = _context({999})
    user = user_service.register_user(db_session, telegram_id=555, full_name="TA")
    user_service.set_admin(db_session, user, True)
    user_service.set_active(db_session, user, False)

    assert auth.is_admin(db_session, 555, context) is False


def test_revoking_db_admin_role_removes_admin_status(db_session):
    context = _context({999})
    user = user_service.register_user(db_session, telegram_id=555, full_name="TA")
    user_service.set_admin(db_session, user, True)
    user_service.set_admin(db_session, user, False)

    assert auth.is_admin(db_session, 555, context) is False
