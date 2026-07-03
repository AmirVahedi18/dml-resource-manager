from datetime import date, datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import fmt_dt, fmt_duration_hours, fmt_ram
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import (
    cancel_wizard,
    handle_back_or_cancel,
    render_paginated_step,
    resolve_preset_or_more,
    show_main_menu,
)
from dml_bot.bot_reply.gpu_picker import gpu_items, render_gpu_step
from dml_bot.bot_reply.keyboards import BACK, CONFIRM, MAIN_MENU, cancel_only_keyboard, confirm_keyboard, preset_keyboard
from dml_bot.bot_reply.presets import fine_ram_options
from dml_bot.bot_reply.states import ReserveStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service
from dml_bot.utils.time_utils import generate_slot_starts, local_day_range_utc, to_local_label, utc_now

MENU_BUTTON = "📅 Reserve GPU"


async def _render_gpu_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_gpu_step(update, context, "Step 1/5 — choose a GPU:", ReserveStates.CHOOSE_GPU)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            await update.effective_message.reply_text(
                "You're not registered yet. Send /myid and ask the lab admin to register you."
            )
            return ConversationHandler.END
        items = gpu_items(session)

    if not items:
        await update.effective_message.reply_text("No GPUs are configured yet.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["_gpu_items"] = items
    context.user_data["_page"] = 0
    return await _render_gpu_step(update, context)


def _date_items(days_visible: int) -> list[tuple[str, str]]:
    return [
        ((date.today() + timedelta(days=i)).strftime("%a %d %b"), (date.today() + timedelta(days=i)).isoformat())
        for i in range(days_visible)
    ]


async def _render_date_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_paginated_step(update, context, "_date_items", "Step 2/5 — choose a date:", ReserveStates.CHOOSE_DATE)


async def choose_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_gpu_step(update, context), lambda: cancel_wizard(update, context)
    )
    if result is not None:
        return result

    gpu_id = resolve_choice(context, update.effective_message.text)
    if gpu_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return ReserveStates.CHOOSE_GPU
    context.user_data["gpu_id"] = gpu_id

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    days_visible = context.application.bot_data["config"].bot.date_picker_days_visible
    days_visible = min(days_visible, regulation.booking_horizon_days)

    context.user_data["_date_items"] = _date_items(days_visible)
    context.user_data["_page"] = 0
    return await _render_date_step(update, context)


async def _render_time_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_paginated_step(
        update, context, "_time_items", "Step 3/5 — choose a start time:", ReserveStates.CHOOSE_START_TIME
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
        return ReserveStates.CHOOSE_DATE
    picked_date = date.fromisoformat(date_str)

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    range_start, range_end = local_day_range_utc(picked_date, tz_name)
    slot_starts = generate_slot_starts(range_start, range_end, regulation.min_reservation_slot_minutes, utc_now())

    if not slot_starts:
        await update.effective_message.reply_text("No reservable time left on that date, pick another date.")
        return await _render_date_step(update, context)

    context.user_data["_time_items"] = [(to_local_label(t, tz_name), t.isoformat()) for t in slot_starts]
    context.user_data["_page"] = 0
    return await _render_time_step(update, context)


async def _render_duration_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    await update.effective_message.reply_text(
        f"Step 4/5 — send a whole number of hours for the duration (1-{regulation.max_duration_hours}):",
        reply_markup=cancel_only_keyboard(),
    )
    return ReserveStates.CHOOSE_DURATION


async def choose_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_time_step(update, context), lambda: _render_date_step(update, context)
    )
    if result is not None:
        return result

    iso_dt = resolve_choice(context, update.effective_message.text)
    if iso_dt is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return ReserveStates.CHOOSE_START_TIME
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
        return ReserveStates.CHOOSE_DURATION

    return await _proceed_to_ram(update, context, hours)


def _ram_free_cap_presets(session, context: ContextTypes.DEFAULT_TYPE) -> tuple[int, int, list[tuple[str, int]]]:
    gpu = session.get(GPU, context.user_data["gpu_id"])
    regulation = regulation_service.get_regulation(session)
    start = datetime.fromisoformat(context.user_data["start_time"])
    end = start + timedelta(hours=context.user_data["duration_hours"])
    free_ram = reservation_service.min_free_ram_in_range(session, gpu, start, end)
    cap = min(free_ram, regulation.max_ram_per_reservation_mb)
    presets = sorted({p for p in (cap // 4, cap // 2, cap) if p > 0})
    return free_ram, cap, [(fmt_ram(p), p) for p in presets]


async def _render_ram_presets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        free_ram, cap, presets = _ram_free_cap_presets(session, context)
    if cap <= 0:
        await update.effective_message.reply_text("No RAM is free for that window. Please try a different time.")
        return await cancel_wizard(update, context)
    markup = preset_keyboard(context, presets)
    await update.effective_message.reply_text(
        f"Free RAM in that window: {fmt_ram(free_ram)}\nStep 5/5 — choose RAM to reserve:", reply_markup=markup
    )
    return ReserveStates.CHOOSE_RAM


async def _render_ram_fine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        _, cap, _ = _ram_free_cap_presets(session, context)
    context.user_data["_ram_fine_items"] = fine_ram_options(cap)
    return await render_paginated_step(update, context, "_ram_fine_items", "Choose RAM to reserve:", ReserveStates.CHOOSE_RAM)


async def _proceed_to_ram(update: Update, context: ContextTypes.DEFAULT_TYPE, hours: int) -> int:
    context.user_data["duration_hours"] = hours
    context.user_data["_ram_mode"] = "preset"
    return await _render_ram_presets(update, context)


async def choose_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    state, ram_mb = await resolve_preset_or_more(
        update,
        context,
        "_ram_mode",
        lambda: _render_ram_presets(update, context),
        lambda: _render_ram_fine(update, context),
        lambda: _render_duration_prompt(update, context),
    )
    if state is not None:
        return state

    context.user_data.pop("_ram_mode", None)
    context.user_data.pop("_page", None)
    return await _show_confirmation(update, context, ram_mb)


async def _show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, ram_mb: int) -> int:
    context.user_data["ram_mb"] = ram_mb

    start = datetime.fromisoformat(context.user_data["start_time"])
    end = start + timedelta(hours=context.user_data["duration_hours"])
    tz_name = context.application.bot_data["config"].bot.timezone

    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
        server = session.get(Server, gpu.server_id)

    text = (
        f"<b>Confirm reservation</b>\n\n"
        f"Server: {server.name}\n"
        f"GPU: {gpu.index_on_server} ({gpu.model_name})\n"
        f"From: {fmt_dt(start, tz_name)}\n"
        f"To: {fmt_dt(end, tz_name)}\n"
        f"Duration: {fmt_duration_hours(context.user_data['duration_hours'])}\n"
        f"RAM: {fmt_ram(ram_mb)}"
    )
    await update.effective_message.reply_text(text, reply_markup=confirm_keyboard(), parse_mode="HTML")
    return ReserveStates.CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        context.user_data["_ram_mode"] = "preset"
        context.user_data.pop("_page", None)
        return await _render_ram_presets(update, context)
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return ReserveStates.CONFIRM

    start = datetime.fromisoformat(context.user_data["start_time"])
    end = start + timedelta(hours=context.user_data["duration_hours"])
    ram_mb = context.user_data["ram_mb"]

    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        gpu = session.get(GPU, context.user_data["gpu_id"])
        regulation = regulation_service.get_regulation(session)
        try:
            reservation_service.create_reservation(session, user, gpu, start, end, ram_mb, regulation)
        except reservation_service.ReservationError as exc:
            await update.effective_message.reply_text(f"Could not create reservation: {exc}")
            context.user_data.clear()
            return ConversationHandler.END

    context.user_data.clear()
    await update.effective_message.reply_text("✅ Reservation confirmed!")
    await show_main_menu(update, context)
    return ConversationHandler.END


def reserve_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            ReserveStates.CHOOSE_GPU: [MessageHandler(text_filter, choose_gpu)],
            ReserveStates.CHOOSE_DATE: [MessageHandler(text_filter, choose_date)],
            ReserveStates.CHOOSE_START_TIME: [MessageHandler(text_filter, choose_start_time)],
            ReserveStates.CHOOSE_DURATION: [MessageHandler(text_filter, choose_duration)],
            ReserveStates.CHOOSE_RAM: [MessageHandler(text_filter, choose_ram)],
            ReserveStates.CONFIRM: [MessageHandler(text_filter, confirm)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_reserve_conversation",
        persistent=False,
    )
