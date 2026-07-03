from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from dml_bot.bot.auth import require_admin
from dml_bot.bot.handlers.common import cancel_wizard_callback, show_main_menu
from dml_bot.bot.keyboards import CANCEL_BUTTON, past_range_picker_keyboard
from dml_bot.bot.states import AdminUsageStates
from dml_bot.charts.usage_charts import render_bar_chart
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, usage_service
from dml_bot.utils.time_utils import local_day_range_utc, utc_now

SCOPE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("👤 By User", callback_data="adminusage:scope:user")],
        [InlineKeyboardButton("🖥 By GPU", callback_data="adminusage:scope:gpu")],
        [CANCEL_BUTTON],
    ]
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    if not await require_admin(update, context):
        return ConversationHandler.END

    await update.callback_query.edit_message_text("Break usage down by:", reply_markup=SCOPE_KEYBOARD)
    return AdminUsageStates.CHOOSE_SCOPE


async def choose_scope(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    scope = update.callback_query.data.split(":")[2]
    context.user_data["scope"] = scope

    await update.callback_query.edit_message_text(
        "Choose a date range:", reply_markup=past_range_picker_keyboard("adminusage")
    )
    return AdminUsageStates.CHOOSE_RANGE


async def choose_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    range_key = update.callback_query.data.split(":")[2]
    scope = context.user_data["scope"]
    tz_name = context.application.bot_data["config"].bot.timezone

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
        now = utc_now()
        if range_key == "today":
            range_start, range_end = local_day_range_utc(now.date(), tz_name)
        elif range_key == "week":
            range_start, range_end = now - timedelta(days=7), now
        elif range_key == "month":
            range_start, range_end = now - timedelta(days=30), now
        else:
            range_start, range_end = now - timedelta(days=regulation.booking_horizon_days), now

        reservations = usage_service.get_reservations_in_range(session, range_start, range_end)

        if scope == "user":
            totals = usage_service.total_gpu_hours_by_user(reservations, range_start, range_end)
            labels = [session.get(User, uid).full_name for uid in totals]
            ylabel = "GPU-hours"
            title = "Usage by user"
        else:
            totals = usage_service.total_ram_hours_by_gpu(reservations, range_start, range_end)
            gpus = {gid: session.get(GPU, gid) for gid in totals}
            labels = [f"{gpus[gid].server.name} GPU{gpus[gid].index_on_server}" for gid in totals]
            ylabel = "MB-hours"
            title = "Usage by GPU"

        values = list(totals.values())

    context.user_data.clear()
    if not values:
        await update.callback_query.edit_message_text("No reservations in that range.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    png_bytes = render_bar_chart(labels, values, title, ylabel)
    await update.effective_message.reply_photo(photo=png_bytes)
    await show_main_menu(update, context)
    return ConversationHandler.END


def usage_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^admin:usage$")],
        states={
            AdminUsageStates.CHOOSE_SCOPE: [
                CallbackQueryHandler(choose_scope, pattern=r"^adminusage:scope:\w+$")
            ],
            AdminUsageStates.CHOOSE_RANGE: [
                CallbackQueryHandler(choose_range, pattern=r"^adminusage:range:\w+$")
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="admin_usage_conversation",
        persistent=False,
    )
