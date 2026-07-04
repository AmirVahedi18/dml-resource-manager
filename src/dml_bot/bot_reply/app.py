from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from dml_bot.bot_reply.handlers.admin.manage_regulation import regulation_conversation
from dml_bot.bot_reply.handlers.admin.manage_servers import servers_conversation
from dml_bot.bot_reply.handlers.admin.manage_users import users_conversation
from dml_bot.bot_reply.handlers.admin.reservations_admin import admin_reservations_conversation
from dml_bot.bot_reply.handlers.admin.usage_report import usage_conversation
from dml_bot.bot_reply.handlers.common import (
    admin_menu_command,
    back_to_main_command,
    cancel_command,
    help_command,
    myid_command,
    show_main_menu,
    start_command,
)
from dml_bot.bot_reply.handlers.student.cancel_reservation import cancel_reservation_conversation
from dml_bot.bot_reply.handlers.student.reserve import reserve_conversation
from dml_bot.bot_reply.handlers.student.view_schedule import schedule_conversation
from dml_bot.bot_reply.handlers.student.watch import watch_conversation
from dml_bot.bot_reply.keyboards import ADMIN_PANEL, BACK_TO_MAIN, HELP
from dml_bot.config.schema import AppConfig


async def _fallback_show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Anything typed outside an active wizard (stray text, a stale/removed keyboard) just
    re-docks the main menu, so the user is never stuck without a visible way forward."""
    await show_main_menu(update, context)


def build_reply_application(token: str, admin_ids: set[int], config: AppConfig) -> Application:
    """Registers the persistent reply-keyboard bot: /start, /help, /myid, /cancel, the top-level
    menu router, then the 4 student + 5 admin conversation wizards."""
    application = Application.builder().token(token).build()
    application.bot_data["admin_ids"] = admin_ids
    application.bot_data["config"] = config

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(MessageHandler(filters.Text([HELP]), help_command))
    application.add_handler(MessageHandler(filters.Text([ADMIN_PANEL]), admin_menu_command))
    application.add_handler(MessageHandler(filters.Text([BACK_TO_MAIN]), back_to_main_command))

    application.add_handler(reserve_conversation())
    application.add_handler(cancel_reservation_conversation())
    application.add_handler(schedule_conversation())
    application.add_handler(watch_conversation())

    application.add_handler(users_conversation())
    application.add_handler(servers_conversation())
    application.add_handler(regulation_conversation())
    application.add_handler(usage_conversation())
    application.add_handler(admin_reservations_conversation())

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _fallback_show_menu))
    return application
