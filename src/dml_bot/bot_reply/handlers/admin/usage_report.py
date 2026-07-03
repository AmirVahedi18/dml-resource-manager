from datetime import timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import require_admin
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import cancel_wizard, show_main_menu
from dml_bot.bot_reply.keyboards import BACK, MAIN_MENU, action_keyboard
from dml_bot.bot_reply.states import AdminUsageStates
from dml_bot.charts.usage_charts import render_bar_chart
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, usage_service
from dml_bot.utils.time_utils import local_day_range_utc, utc_now

MENU_BUTTON = "📊 Usage Report"
PAST_RANGE_PRESETS = [
    ("Today", "today"),
    ("Past week", "week"),
    ("Past 30 days", "month"),
    ("Full booking horizon", "horizon"),
]


async def _render_scope_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    markup = action_keyboard(context, [("👤 By User", "user"), ("🖥 By GPU", "gpu")])
    await update.effective_message.reply_text("Break usage down by:", reply_markup=markup)
    return AdminUsageStates.CHOOSE_SCOPE


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_admin(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    return await _render_scope_step(update, context)


async def _render_range_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    markup = action_keyboard(context, PAST_RANGE_PRESETS)
    await update.effective_message.reply_text("Choose a date range:", reply_markup=markup)
    return AdminUsageStates.CHOOSE_RANGE


async def choose_scope(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text in (MAIN_MENU, BACK):  # this is the first screen, so Back also exits
        return await cancel_wizard(update, context)

    scope = resolve_choice(context, text)
    if scope is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminUsageStates.CHOOSE_SCOPE

    context.user_data["scope"] = scope
    return await _render_range_step(update, context)


async def choose_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_scope_step(update, context)

    range_key = resolve_choice(context, text)
    if range_key is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminUsageStates.CHOOSE_RANGE

    scope = context.user_data["scope"]
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
        now = utc_now()
        if range_key == "today":
            range_start, range_end = local_day_range_utc(now.date(), context.application.bot_data["config"].bot.timezone)
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
        await update.effective_message.reply_text("No reservations in that range.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    png_bytes = render_bar_chart(labels, values, title, ylabel)
    await update.effective_message.reply_photo(photo=png_bytes)
    await show_main_menu(update, context)
    return ConversationHandler.END


def usage_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            AdminUsageStates.CHOOSE_SCOPE: [MessageHandler(text_filter, choose_scope)],
            AdminUsageStates.CHOOSE_RANGE: [MessageHandler(text_filter, choose_range)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_admin_usage_conversation",
        persistent=False,
    )
