from datetime import timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import fmt_ram
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.gpu_picker import gpu_items, render_gpu_step
from dml_bot.bot_reply.handlers.common import cancel_wizard, handle_back_or_cancel, show_main_menu
from dml_bot.bot_reply.keyboards import BACK, MAIN_MENU, action_keyboard
from dml_bot.bot_reply.ram_chart import render_ram_chart
from dml_bot.bot_reply.states import ScheduleStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service
from dml_bot.utils.time_utils import local_day_range_utc, to_local_label, utc_now

MENU_BUTTON = "🗓 Schedule"


def _range_presets(config, booking_horizon_days: int) -> list[tuple[str, int]]:
    options = [("Today", 0)]
    for days in config.schedule_chart.range_days_options:
        if days <= booking_horizon_days:
            options.append((f"{days} days", days))
    return options


def _range_label(days: int) -> str:
    return "today" if days == 0 else f"the next {days} days"


async def _render_gpu_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_gpu_step(update, context, "Step 1/2 — choose a GPU:", ScheduleStates.CHOOSE_GPU)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            await update.effective_message.reply_text("You're not registered yet.")
            return ConversationHandler.END
        items = gpu_items(session)

    if not items:
        await update.effective_message.reply_text("No GPUs are configured yet.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["_gpu_items"] = items
    context.user_data["_page"] = 0
    return await _render_gpu_step(update, context)


async def _render_range_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config = context.application.bot_data["config"]
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    markup = action_keyboard(context, _range_presets(config, regulation.booking_horizon_days))
    await update.effective_message.reply_text("Step 2/2 — choose a date range:", reply_markup=markup)
    return ScheduleStates.CHOOSE_RANGE


async def choose_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_gpu_step(update, context), lambda: cancel_wizard(update, context)
    )
    if result is not None:
        return result

    gpu_id = resolve_choice(context, update.effective_message.text)
    if gpu_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return ScheduleStates.CHOOSE_GPU
    context.user_data["gpu_id"] = gpu_id

    return await _render_range_step(update, context)


async def choose_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_gpu_step(update, context)

    days = resolve_choice(context, text)
    if days is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return ScheduleStates.CHOOSE_RANGE

    config = context.application.bot_data["config"]
    tz_name = config.bot.timezone
    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
        server = session.get(Server, gpu.server_id)

        now = utc_now()
        if days == 0:
            range_start, range_end = local_day_range_utc(now.date(), tz_name)
        else:
            range_start, range_end = now, now + timedelta(days=days)

        reservations = reservation_service.list_reservations_for_gpu(session, gpu.id, range_start, range_end)
        reservations.sort(key=lambda r: r.start_time)
        lines = [
            f"{to_local_label(r.start_time, tz_name, '%b %d %H:%M')} → "
            f"{to_local_label(r.end_time, tz_name, '%b %d %H:%M')} · {r.user.full_name} · {fmt_ram(r.ram_mb)}"
            for r in reservations
        ]

    chart_pages = render_ram_chart(
        reservations,
        gpu.total_ram_mb,
        range_start,
        range_end,
        tz_name,
        config.schedule_chart.bucket_hours,
        config.schedule_chart.max_width_chars,
    )

    header = f"<b>{server.name} GPU{gpu.index_on_server}</b> — {_range_label(days)}"
    await update.effective_message.reply_text(header, parse_mode="HTML")
    for page in chart_pages:
        await update.effective_message.reply_text(f"<pre>{page}</pre>", parse_mode="HTML")

    body = "\n".join(lines) if lines else "Fully free in this range."
    await update.effective_message.reply_text(f"{body}\n\n(times shown in {tz_name})", parse_mode="HTML")

    context.user_data.clear()
    await show_main_menu(update, context)
    return ConversationHandler.END


def schedule_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            ScheduleStates.CHOOSE_GPU: [MessageHandler(text_filter, choose_gpu)],
            ScheduleStates.CHOOSE_RANGE: [MessageHandler(text_filter, choose_range)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_schedule_conversation",
        persistent=False,
    )
