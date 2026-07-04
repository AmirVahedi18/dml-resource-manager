from datetime import date, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import require_admin
from dml_bot.bot.formatting import fmt_dt, fmt_ram
from dml_bot.bot_reply.chart_delivery import send_ram_chart
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.gpu_picker import gpu_items, render_gpu_step
from dml_bot.bot_reply.handlers.common import cancel_wizard, cancel_wizard_to_admin, show_main_menu
from dml_bot.bot_reply.keyboards import BACK, MAIN_MENU, action_keyboard, cancel_only_keyboard
from dml_bot.bot_reply.states import AdminUsageStates
from dml_bot.charts.usage_charts import render_bar_chart
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, usage_service
from dml_bot.utils.time_utils import local_day_range_utc, utc_now

MENU_BUTTON = "📊 Usage Report"
PAST_RANGE_PRESETS = [
    ("Today", "today"),
    ("Past week", "week"),
    ("Past 30 days", "month"),
    ("Full booking horizon", "horizon"),
]
RANGE_LABELS = {key: label for label, key in PAST_RANGE_PRESETS}
HISTORICAL_SCOPE = "historical"


def _historical_bucket_hours(days: int) -> float:
    """Scales the availability chart's bucket size to the requested window, so an admin looking
    back over months doesn't get a chart with thousands of buckets -- reservations themselves are
    kept forever (see `scheduling.jobs.run_cleanup`), but the chart has to stay legible/fast
    regardless of how far back the window reaches."""
    if days <= 2:
        return 1.0
    if days <= 7:
        return 3.0
    if days <= 30:
        return 12.0
    if days <= 120:
        return 24.0
    return 24.0 * 7


async def _render_scope_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    markup = action_keyboard(
        context, [("👤 By User", "user"), ("🖥 By GPU", "gpu"), ("📅 Historical Availability", HISTORICAL_SCOPE)]
    )
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


async def _render_historical_gpu_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_gpu_step(update, context, "Step 1/3 — choose a GPU:", AdminUsageStates.CHOOSE_HISTORICAL_GPU)


async def choose_scope(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:  # this is the first screen, so Back steps up to the Admin Panel menu
        return await cancel_wizard_to_admin(update, context)

    scope = resolve_choice(context, text)
    if scope is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminUsageStates.CHOOSE_SCOPE

    context.user_data["scope"] = scope
    if scope == HISTORICAL_SCOPE:
        with session_scope() as session:
            items = gpu_items(session)  # admin: unrestricted, every server's GPUs
        if not items:
            await update.effective_message.reply_text("No GPUs are configured yet.")
            await show_main_menu(update, context)
            return ConversationHandler.END
        context.user_data["_gpu_items"] = items
        context.user_data["_page"] = 0
        return await _render_historical_gpu_step(update, context)

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

        range_label = RANGE_LABELS[range_key]
        if scope == "user":
            totals = usage_service.total_gpu_hours_by_user(reservations, range_start, range_end)
            labels = [session.get(User, uid).full_name for uid in totals]
            ylabel = "GPU-hours"
            title = f"Usage by user — {range_label}"
            values = list(totals.values())
        else:
            totals = usage_service.total_ram_hours_by_gpu(reservations, range_start, range_end)
            gpus = {gid: session.get(GPU, gid) for gid in totals}
            labels = [
                f"{gpus[gid].server.name} GPU{gpus[gid].index_on_server} ({fmt_ram(gpus[gid].total_ram_mb)})"
                for gid in totals
            ]
            ylabel = "GB-hours"
            title = f"Usage by GPU — {range_label}"
            values = [mb_hours / 1024 for mb_hours in totals.values()]  # MB-hours -> GB-hours

    context.user_data.clear()
    if not values:
        await update.effective_message.reply_text("No reservations in that range.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    png_bytes = render_bar_chart(labels, values, title, ylabel)
    await update.effective_message.reply_photo(photo=png_bytes)
    await show_main_menu(update, context)
    return ConversationHandler.END


async def choose_historical_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_scope_step(update, context)

    gpu_id = resolve_choice(context, text)
    if gpu_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminUsageStates.CHOOSE_HISTORICAL_GPU
    context.user_data["gpu_id"] = gpu_id

    await update.effective_message.reply_text(
        "Step 2/3 — send the start date to look back from (YYYY-MM-DD):",
        reply_markup=cancel_only_keyboard(),
    )
    return AdminUsageStates.TYPE_HISTORICAL_START_DATE


async def receive_historical_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_historical_gpu_step(update, context)

    try:
        start_date = date.fromisoformat(text)
    except ValueError:
        await update.effective_message.reply_text("Please send a valid date as YYYY-MM-DD.")
        return AdminUsageStates.TYPE_HISTORICAL_START_DATE

    context.user_data["historical_start_date"] = start_date.isoformat()
    await update.effective_message.reply_text(
        "Step 3/3 — send how many days forward from that date to show:",
        reply_markup=cancel_only_keyboard(),
    )
    return AdminUsageStates.TYPE_HISTORICAL_DURATION_DAYS


async def receive_historical_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        await update.effective_message.reply_text(
            "Step 2/3 — send the start date to look back from (YYYY-MM-DD):",
            reply_markup=cancel_only_keyboard(),
        )
        return AdminUsageStates.TYPE_HISTORICAL_START_DATE

    try:
        days = int(text)
        if days < 1:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Please send a positive whole number of days.")
        return AdminUsageStates.TYPE_HISTORICAL_DURATION_DAYS

    tz_name = context.application.bot_data["config"].bot.timezone
    start_date = date.fromisoformat(context.user_data["historical_start_date"])
    range_start, _ = local_day_range_utc(start_date, tz_name)
    range_end = range_start + timedelta(days=days)

    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
        server = session.get(Server, gpu.server_id)
        reservations = reservation_service.list_reservations_for_gpu(session, gpu.id, range_start, range_end)
        cap_mb = gpu.total_ram_mb
        label = f"{server.name} GPU{gpu.index_on_server}"

    window_label = f"{fmt_dt(range_start, tz_name)} → {fmt_dt(range_end, tz_name)}"
    await send_ram_chart(
        update, context, reservations, cap_mb, range_start, range_end, tz_name,
        header_html=f"<b>{label}</b> — historical availability ({window_label})",
        title_plain=f"{label} — historical availability ({window_label})",
        bucket_hours=_historical_bucket_hours(days),
    )

    context.user_data.clear()
    await show_main_menu(update, context)
    return ConversationHandler.END


def usage_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            AdminUsageStates.CHOOSE_SCOPE: [MessageHandler(text_filter, choose_scope)],
            AdminUsageStates.CHOOSE_RANGE: [MessageHandler(text_filter, choose_range)],
            AdminUsageStates.CHOOSE_HISTORICAL_GPU: [MessageHandler(text_filter, choose_historical_gpu)],
            AdminUsageStates.TYPE_HISTORICAL_START_DATE: [MessageHandler(text_filter, receive_historical_start_date)],
            AdminUsageStates.TYPE_HISTORICAL_DURATION_DAYS: [MessageHandler(text_filter, receive_historical_duration)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_admin_usage_conversation",
        persistent=False,
    )
