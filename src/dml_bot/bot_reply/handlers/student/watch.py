from datetime import date, datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import fmt_dt, fmt_duration_hours, fmt_ram, watch_summary
from dml_bot.bot_reply.chart_delivery import send_ram_chart
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.gpu_picker import accessible_server_ids_for, gpu_items, render_gpu_step
from dml_bot.bot_reply.handlers.common import (
    cancel_wizard,
    finish_admin_self_registration,
    handle_back_or_cancel,
    prompt_admin_self_registration,
    render_paginated_step,
    show_main_menu,
)
from dml_bot.bot_reply.keyboards import (
    BACK,
    CONFIRM,
    MAIN_MENU,
    action_keyboard,
    cancel_only_keyboard,
    confirm_keyboard,
    paginated_list_keyboard,
)
from dml_bot.bot_reply.presets import ram_unit_mb
from dml_bot.bot_reply.states import WatchFlowStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.models.watch import WatchSubscription
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, watch_service
from dml_bot.utils.time_utils import generate_slot_starts, local_day_range_utc, to_local_label, utc_now

MENU_BUTTON = "🔔 Watches"
NEW_WATCH = "➕ New Watch"
AUTO_BOOK_CHOICES = [("✅ Yes, auto-book", True), ("🔕 No, just notify", False)]


def _watch_items(session, user_id: int, tz_name: str) -> list[tuple[str, int]]:
    """Reply-keyboard button labels are always plain text (Telegram buttons can't render HTML
    markup), unlike `watch_summary`'s `<b>...</b>` tags used for the message body below."""
    watches = watch_service.list_watches_for_user(session, user_id)
    return [
        (
            f"❌ {w.gpu.server.name} GPU{w.gpu.index_on_server} · "
            f"{fmt_dt(w.range_start, tz_name)} → {fmt_dt(w.range_end, tz_name)}",
            w.id,
        )
        for w in watches
    ]


async def _render_menu_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    items = context.user_data.get("_watch_items", [])
    page = context.user_data.get("_page", 0)
    markup = paginated_list_keyboard(context, items, page, extra_rows=[[NEW_WATCH]])
    text = "Your active watches (tap to cancel), or add a new one:" if items else "You have no active watches."
    await update.effective_message.reply_text(text, reply_markup=markup)
    return WatchFlowStates.MENU


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            if await prompt_admin_self_registration(update, context):
                return WatchFlowStates.AWAITING_ADMIN_NAME
            await update.effective_message.reply_text("You're not registered yet.")
            return ConversationHandler.END
        items = _watch_items(session, user.id, tz_name)

    context.user_data.clear()
    context.user_data["_watch_items"] = items
    context.user_data["_page"] = 0
    return await _render_menu_step(update, context)


async def _render_gpu_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_gpu_step(update, context, "Step 1/5 — choose a GPU:", WatchFlowStates.CHOOSE_GPU)


async def new_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        accessible_ids = accessible_server_ids_for(session, update.effective_user.id, user.id, context)
        items = gpu_items(session, accessible_ids)
    if not items:
        text = (
            "No GPUs are configured yet."
            if accessible_ids is None
            else "You don't have access to any servers yet. Ask the lab admin to grant you access."
        )
        await update.effective_message.reply_text(text)
        return ConversationHandler.END
    context.user_data["_gpu_items"] = items
    context.user_data["_page"] = 0
    return await _render_gpu_step(update, context)


async def menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == NEW_WATCH:
        return await new_watch(update, context)

    result = await handle_back_or_cancel(
        update, context, lambda: _render_menu_step(update, context), lambda: cancel_wizard(update, context)
    )
    if result is not None:
        return result

    watch_id = resolve_choice(context, text)
    if watch_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.MENU
    context.user_data["watch_id"] = watch_id

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        watch = session.get(WatchSubscription, watch_id)
        text_out = "Cancel this watch?\n\n" + watch_summary(watch, watch.gpu, watch.gpu.server, tz_name)
    await update.effective_message.reply_text(text_out, reply_markup=confirm_keyboard(), parse_mode="HTML")
    return WatchFlowStates.CONFIRM_CANCEL


async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_menu_step(update, context)
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.CONFIRM_CANCEL

    with session_scope() as session:
        watch = session.get(WatchSubscription, context.user_data["watch_id"])
        watch_service.cancel_watch(session, watch)

    context.user_data.clear()
    await update.effective_message.reply_text("✅ Watch cancelled.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def _date_items(days_visible: int) -> list[tuple[str, str]]:
    return [
        ((date.today() + timedelta(days=i)).strftime("%a %d %b"), (date.today() + timedelta(days=i)).isoformat())
        for i in range(days_visible)
    ]


async def _render_date_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    grid = context.application.bot_data["config"].list_grids.date
    return await render_paginated_step(
        update, context, "_date_items", "Step 2/5 — choose a start date:", WatchFlowStates.CHOOSE_DATE,
        columns=grid.columns, rows=grid.rows,
    )


async def _send_availability_chart(update: Update, context: ContextTypes.DEFAULT_TYPE, gpu_id: int, days: int) -> None:
    """Same RAM-occupancy chart shown before Reserve GPU's date step, so a student can see the
    GPU's current load before picking a window to watch for it to free up."""
    tz_name = context.application.bot_data["config"].bot.timezone
    now = utc_now()
    range_start, range_end = now, now + timedelta(days=days)

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        server = session.get(Server, gpu.server_id)
        reservations = reservation_service.list_reservations_for_gpu(session, gpu.id, range_start, range_end)
        cap_mb = gpu.total_ram_mb
        label = f"{server.name} GPU{gpu.index_on_server}"

    await send_ram_chart(
        update, context, reservations, cap_mb, range_start, range_end, tz_name,
        header_html=f"<b>{label}</b> — availability for the next {days} day(s)",
        title_plain=f"{label} — availability for the next {days} day(s)",
    )


async def choose_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_gpu_step(update, context), lambda: _render_menu_step(update, context)
    )
    if result is not None:
        return result

    gpu_id = resolve_choice(context, update.effective_message.text)
    if gpu_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.CHOOSE_GPU
    context.user_data["gpu_id"] = gpu_id

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    days_visible = context.application.bot_data["config"].bot.date_picker_days_visible
    days_visible = min(days_visible, regulation.booking_horizon_days)

    await _send_availability_chart(update, context, gpu_id, days_visible)

    context.user_data["_date_items"] = _date_items(days_visible)
    context.user_data["_page"] = 0
    return await _render_date_step(update, context)


async def _render_time_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    grid = context.application.bot_data["config"].list_grids.start_time
    return await render_paginated_step(
        update, context, "_time_items", "Step 3/5 — choose a start time:", WatchFlowStates.CHOOSE_START_TIME,
        columns=grid.columns, rows=grid.rows,
    )


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_date_step(update, context), lambda: _render_gpu_step(update, context)
    )
    if result is not None:
        return result

    date_str = resolve_choice(context, update.effective_message.text)
    if date_str is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.CHOOSE_DATE
    picked_date = date.fromisoformat(date_str)

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    range_start, range_end = local_day_range_utc(picked_date, tz_name)
    slot_starts = generate_slot_starts(range_start, range_end, regulation.min_reservation_slot_minutes, utc_now())

    if not slot_starts:
        await update.effective_message.reply_text("No time left on that date, pick another date.")
        return await _render_date_step(update, context)

    context.user_data["_time_items"] = [(to_local_label(t, tz_name), t.isoformat()) for t in slot_starts]
    context.user_data["_page"] = 0
    return await _render_time_step(update, context)


async def _render_duration_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    await update.effective_message.reply_text(
        f"Step 4/5 — send a whole number of hours for how long the window should last "
        f"(1-{regulation.max_duration_hours}):",
        reply_markup=cancel_only_keyboard(),
    )
    return WatchFlowStates.CHOOSE_DURATION


async def choose_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_time_step(update, context), lambda: _render_date_step(update, context)
    )
    if result is not None:
        return result

    iso_dt = resolve_choice(context, update.effective_message.text)
    if iso_dt is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.CHOOSE_START_TIME
    context.user_data["start_time"] = iso_dt
    context.user_data.pop("_page", None)
    return await _render_duration_prompt(update, context)


async def choose_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_time_step(update, context)

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    try:
        hours = int(text)
        if not (1 <= hours <= regulation.max_duration_hours):
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            f"Please send a whole number of hours from 1 to {regulation.max_duration_hours}."
        )
        return WatchFlowStates.CHOOSE_DURATION

    context.user_data["duration_hours"] = hours
    return await _render_ram_prompt(update, context)


async def _render_ram_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
    unit = context.application.bot_data["config"].ram_input.unit
    unit_mb = ram_unit_mb(unit)
    max_units = gpu.total_ram_mb // unit_mb
    await update.effective_message.reply_text(
        f"Step 5/5 — send a whole number of {unit} for the minimum RAM you need to be notified "
        f"about (1-{max_units}):",
        reply_markup=cancel_only_keyboard(),
    )
    return WatchFlowStates.CHOOSE_RAM


async def choose_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_duration_prompt(update, context)

    unit = context.application.bot_data["config"].ram_input.unit
    unit_mb = ram_unit_mb(unit)
    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
    max_units = gpu.total_ram_mb // unit_mb
    try:
        units = int(text)
        if not (1 <= units <= max_units):
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(
            f"Please send a whole number of {unit} from 1 to {max_units}."
        )
        return WatchFlowStates.CHOOSE_RAM
    context.user_data["ram_mb"] = units * unit_mb
    return await _show_confirmation(update, context)


async def _show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    start = datetime.fromisoformat(context.user_data["start_time"])
    end = start + timedelta(hours=context.user_data["duration_hours"])
    tz_name = context.application.bot_data["config"].bot.timezone

    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
        server = session.get(Server, gpu.server_id)

    text = (
        f"<b>Confirm watch</b>\n\n"
        f"Server: {server.name}\n"
        f"GPU: {gpu.index_on_server} ({gpu.model_name})\n"
        f"From: {fmt_dt(start, tz_name)}\n"
        f"To: {fmt_dt(end, tz_name)}\n"
        f"Duration: {fmt_duration_hours(context.user_data['duration_hours'])}\n"
        f"Minimum RAM: {fmt_ram(context.user_data['ram_mb'])}\n\n"
        "Auto-book the slot the instant it frees (from whenever it frees, capped by the lab's "
        "max reservation duration), or just get notified so you can pick manually?"
    )
    markup = action_keyboard(context, AUTO_BOOK_CHOICES)
    await update.effective_message.reply_text(text, reply_markup=markup, parse_mode="HTML")
    return WatchFlowStates.CHOOSE_AUTO_BOOK


async def choose_auto_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_ram_prompt(update, context)

    auto_book = resolve_choice(context, text)
    if auto_book is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.CHOOSE_AUTO_BOOK

    start = datetime.fromisoformat(context.user_data["start_time"])
    end = start + timedelta(hours=context.user_data["duration_hours"])

    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        gpu = session.get(GPU, context.user_data["gpu_id"])
        watch_service.create_watch(
            session, user, gpu, start, end, context.user_data["ram_mb"], auto_book=auto_book
        )

    context.user_data.clear()
    text_out = (
        "✅ Watch created — the slot will be booked for you automatically the instant it frees."
        if auto_book
        else "✅ Watch created — you'll be notified when enough RAM frees up."
    )
    await update.effective_message.reply_text(text_out)
    await show_main_menu(update, context)
    return ConversationHandler.END


def watch_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            WatchFlowStates.MENU: [MessageHandler(text_filter, menu_choice)],
            WatchFlowStates.CONFIRM_CANCEL: [MessageHandler(text_filter, confirm_cancel)],
            WatchFlowStates.CHOOSE_GPU: [MessageHandler(text_filter, choose_gpu)],
            WatchFlowStates.CHOOSE_DATE: [MessageHandler(text_filter, choose_date)],
            WatchFlowStates.CHOOSE_START_TIME: [MessageHandler(text_filter, choose_start_time)],
            WatchFlowStates.CHOOSE_DURATION: [MessageHandler(text_filter, choose_duration)],
            WatchFlowStates.CHOOSE_RAM: [MessageHandler(text_filter, choose_ram)],
            WatchFlowStates.CHOOSE_AUTO_BOOK: [MessageHandler(text_filter, choose_auto_book)],
            WatchFlowStates.AWAITING_ADMIN_NAME: [
                MessageHandler(
                    text_filter,
                    lambda u, c: finish_admin_self_registration(u, c, WatchFlowStates.AWAITING_ADMIN_NAME, start),
                )
            ],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_watch_conversation",
        persistent=False,
    )
