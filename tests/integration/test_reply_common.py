from dml_bot.bot_reply.handlers import common
from tests.integration.telegram_helpers import FakeBot, make_context, make_text_update

STUDENT_TELEGRAM_ID = 555
ADMIN_TELEGRAM_ID = 999


async def test_help_command_sends_only_student_help_to_non_admins():
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    update = make_text_update(1, STUDENT_TELEGRAM_ID, "/help", bot)

    await common.help_command(update, context)

    bot.send_message.assert_awaited_once()
    text = bot.send_message.call_args.kwargs["text"]
    assert "Reserve GPU" in text
    assert "Admin Panel" not in text


async def test_help_command_sends_student_and_admin_help_to_admins():
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
