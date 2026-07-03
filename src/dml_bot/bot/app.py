from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from dml_bot.bot.handlers.admin.manage_regulation import regulation_conversation
from dml_bot.bot.handlers.admin.manage_servers import servers_conversation
from dml_bot.bot.handlers.admin.manage_users import users_conversation
from dml_bot.bot.handlers.admin.reservations_admin import admin_reservations_conversation
from dml_bot.bot.handlers.admin.usage_report import usage_conversation
from dml_bot.bot.handlers.common import (
    admin_menu_callback,
    cancel_command,
    help_command,
    main_menu_callback,
    myid_command,
    start_command,
)
from dml_bot.bot.handlers.student.cancel_reservation import cancel_reservation_conversation
from dml_bot.bot.handlers.student.reserve import reserve_conversation
from dml_bot.bot.handlers.student.view_schedule import schedule_conversation
from dml_bot.bot.handlers.student.watch import watch_conversation
from dml_bot.config.schema import AppConfig


def build_application(token: str, admin_ids: set[int], config: AppConfig) -> Application:
    """Registers `/start`, `/help`, `/myid` always (identity/registration works the same in either
    mode); the full classic conversational menu is only registered when `config.interface ==
    "legacy"` -- in "webapp" mode all reservation/admin features live in the Mini App instead, so
    wiring up the classic wizards too would just give users two divergent ways to do the same
    thing."""
    application = Application.builder().token(token).build()
    application.bot_data["admin_ids"] = admin_ids
    application.bot_data["config"] = config

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid_command))

    if config.interface == "legacy":
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^menu:main$"))
        application.add_handler(CallbackQueryHandler(help_command, pattern="^menu:help$"))
        application.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^menu:admin$"))

        application.add_handler(reserve_conversation())
        application.add_handler(cancel_reservation_conversation())
        application.add_handler(schedule_conversation())
        application.add_handler(watch_conversation())

        application.add_handler(users_conversation())
        application.add_handler(servers_conversation())
        application.add_handler(regulation_conversation())
        application.add_handler(usage_conversation())
        application.add_handler(admin_reservations_conversation())

    return application
