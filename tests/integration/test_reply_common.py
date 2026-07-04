from dml_bot.bot_reply.handlers import common
from dml_bot.db.session import session_scope
from dml_bot.services import invite_service, user_service
from tests.integration.telegram_helpers import FakeBot, make_context, make_text_update

STUDENT_TELEGRAM_ID = 555
ADMIN_TELEGRAM_ID = 999


async def test_start_without_invite_code_tells_student_to_get_one(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    update = make_text_update(1, 777, "/start", bot)

    await common.start_command(update, context)

    assert "invite code" in bot.send_message.call_args.kwargs["text"]


async def test_start_with_valid_invite_code_registers_student(lab_setup):
    with session_scope() as session:
        invite = invite_service.create_invite(session, full_name="Charlie")
        code = invite.code

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID}, args=[code])
    update = make_text_update(1, 777, f"/start {code}", bot)

    await common.start_command(update, context)

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, 777)
        assert user is not None
        assert user.full_name == "Charlie"


async def test_help_command_sends_only_student_help_to_non_admins(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    update = make_text_update(1, STUDENT_TELEGRAM_ID, "/help", bot)

    await common.help_command(update, context)

    bot.send_message.assert_awaited_once()
    text = bot.send_message.call_args.kwargs["text"]
    assert "Reserve GPU" in text
    assert "Admin Panel" not in text


async def test_help_command_sends_student_and_admin_help_to_admins(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    update = make_text_update(1, ADMIN_TELEGRAM_ID, "/help", bot)

    await common.help_command(update, context)

    assert bot.send_message.await_count == 2
    student_text = bot.send_message.call_args_list[0].kwargs["text"]
    admin_text = bot.send_message.call_args_list[1].kwargs["text"]
    assert "Reserve GPU" in student_text
    assert "Admin Panel" in admin_text
    assert "Manage Users" in admin_text
