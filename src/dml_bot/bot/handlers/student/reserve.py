from datetime import date, datetime, timedelta

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import fmt_dt, fmt_duration_hours, fmt_ram
from dml_bot.bot.handlers.common import cancel_wizard_callback, show_main_menu
from dml_bot.bot.keyboards import (
    cancel_only_keyboard,
    confirm_keyboard,
    date_picker_keyboard,
    duration_keyboard,
    gpu_list_keyboard,
    ram_keyboard,
    server_list_keyboard,
    time_picker_keyboard,
)
from dml_bot.bot.states import ReserveStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, server_service
from dml_bot.utils.time_utils import generate_slot_starts, local_day_range_utc, to_local_label, utc_now

DURATION_PRESETS_HOURS = [1, 2, 4, 8]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            await update.callback_query.edit_message_text(
                "You're not registered yet. Send /myid and ask the lab admin to register you."
            )
            return ConversationHandler.END
        servers = server_service.list_servers(session)

    if not servers:
        await update.callback_query.edit_message_text("No servers are configured yet.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.callback_query.edit_message_text(
        "Step 1/6 — choose a server:", reply_markup=server_list_keyboard(servers, "reserve")
    )
    return ReserveStates.CHOOSE_SERVER


async def choose_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    server_id = int(update.callback_query.data.split(":")[2])
    context.user_data["server_id"] = server_id

    with session_scope() as session:
        server = session.get(Server, server_id)
        gpus = server_service.list_gpus(session, server)

    if not gpus:
        await update.callback_query.edit_message_text("This server has no active GPUs.")
        return ConversationHandler.END

    await update.callback_query.edit_message_text(
        f"Server: {server.name}\nStep 2/6 — choose a GPU:", reply_markup=gpu_list_keyboard(gpus, "reserve")
    )
    return ReserveStates.CHOOSE_GPU


async def choose_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    gpu_id = int(update.callback_query.data.split(":")[2])
    context.user_data["gpu_id"] = gpu_id

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)

    days_visible = context.application.bot_data["config"].bot.date_picker_days_visible
    days_visible = min(days_visible, regulation.booking_horizon_days)
    await update.callback_query.edit_message_text(
        "Step 3/6 — choose a date:",
        reply_markup=date_picker_keyboard(date.today(), days_visible, "reserve"),
    )
    return ReserveStates.CHOOSE_DATE


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    date_str = update.callback_query.data.split(":")[2]
    picked_date = date.fromisoformat(date_str)
    context.user_data["date"] = date_str

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)

    range_start, range_end = local_day_range_utc(picked_date, tz_name)
    slot_starts = generate_slot_starts(
        range_start, range_end, regulation.min_reservation_slot_minutes, utc_now()
    )
    if not slot_starts:
        await update.callback_query.edit_message_text(
            "No reservable time left on that date, pick another date.",
            reply_markup=cancel_only_keyboard(),
        )
        return ReserveStates.CHOOSE_DATE

    slots = [(to_local_label(t, tz_name), t) for t in slot_starts]
    await update.callback_query.edit_message_text(
        "Step 4/6 — choose a start time:", reply_markup=time_picker_keyboard(slots, "reserve")
    )
    return ReserveStates.CHOOSE_START_TIME


async def choose_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    iso_dt = update.callback_query.data.split(":", 2)[2]
    context.user_data["start_time"] = iso_dt

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    presets = [h for h in DURATION_PRESETS_HOURS if h <= regulation.max_duration_hours]

    await update.callback_query.edit_message_text(
        "Step 5/6 — choose a duration:", reply_markup=duration_keyboard(presets, "reserve")
    )
    return ReserveStates.CHOOSE_DURATION


async def choose_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    value = update.callback_query.data.split(":")[2]
    if value == "custom":
        await update.callback_query.edit_message_text(
            "Type the duration in hours (e.g. 3 or 1.5):", reply_markup=cancel_only_keyboard()
        )
        return ReserveStates.CHOOSE_DURATION
    return await _proceed_to_ram(update, context, float(value))


async def choose_duration_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        hours = float(update.message.text.strip())
        if hours <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a positive number of hours, e.g. 2.5")
        return ReserveStates.CHOOSE_DURATION
    return await _proceed_to_ram(update, context, hours, via_message=True)


async def _proceed_to_ram(update: Update, context: ContextTypes.DEFAULT_TYPE, hours: float, via_message: bool = False) -> int:
    context.user_data["duration_hours"] = hours

    gpu_id = context.user_data["gpu_id"]
    start = datetime.fromisoformat(context.user_data["start_time"])
    end = start + timedelta(hours=hours)

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        free_ram = reservation_service.min_free_ram_in_range(session, gpu, start, end)

    cap = min(free_ram, regulation.max_ram_per_reservation_mb)
    if cap <= 0:
        text = "No RAM is free for that window. Please /cancel and try a different time."
        if via_message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        return ConversationHandler.END

    presets = sorted({p for p in (cap // 4, cap // 2, cap) if p > 0})
    text = f"Free RAM in that window: {fmt_ram(free_ram)}\nStep 6/6 — choose RAM to reserve:"
    markup = ram_keyboard(presets, "reserve")
    if via_message:
        await update.message.reply_text(text, reply_markup=markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    return ReserveStates.CHOOSE_RAM


async def choose_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    value = update.callback_query.data.split(":")[2]
    if value == "custom":
        await update.callback_query.edit_message_text(
            "Type the amount of RAM in MB (e.g. 4096):", reply_markup=cancel_only_keyboard()
        )
        return ReserveStates.CHOOSE_RAM
    return await _show_confirmation(update, context, int(value))


async def choose_ram_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        ram_mb = int(update.message.text.strip())
        if ram_mb <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a positive whole number of MB, e.g. 4096")
        return ReserveStates.CHOOSE_RAM
    return await _show_confirmation(update, context, ram_mb, via_message=True)


async def _show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, ram_mb: int, via_message: bool = False) -> int:
    context.user_data["ram_mb"] = ram_mb

    start = datetime.fromisoformat(context.user_data["start_time"])
    end = start + timedelta(hours=context.user_data["duration_hours"])
    tz_name = context.application.bot_data["config"].bot.timezone

    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
        server = session.get(Server, context.user_data["server_id"])

    text = (
        f"<b>Confirm reservation</b>\n\n"
        f"Server: {server.name}\n"
        f"GPU: {gpu.index_on_server} ({gpu.model_name})\n"
        f"From: {fmt_dt(start, tz_name)}\n"
        f"To: {fmt_dt(end, tz_name)}\n"
        f"Duration: {fmt_duration_hours(context.user_data['duration_hours'])}\n"
        f"RAM: {fmt_ram(ram_mb)}"
    )
    markup = confirm_keyboard("reserve")
    if via_message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    return ReserveStates.CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
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
            await update.callback_query.edit_message_text(f"Could not create reservation: {exc}")
            context.user_data.clear()
            return ConversationHandler.END

    context.user_data.clear()
    await update.callback_query.edit_message_text("✅ Reservation confirmed!")
    await show_main_menu(update, context)
    return ConversationHandler.END


def reserve_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^menu:reserve$")],
        states={
            ReserveStates.CHOOSE_SERVER: [CallbackQueryHandler(choose_server, pattern=r"^reserve:server:\d+$")],
            ReserveStates.CHOOSE_GPU: [CallbackQueryHandler(choose_gpu, pattern=r"^reserve:gpu:\d+$")],
            ReserveStates.CHOOSE_DATE: [CallbackQueryHandler(choose_date, pattern=r"^reserve:date:.+$")],
            ReserveStates.CHOOSE_START_TIME: [
                CallbackQueryHandler(choose_start_time, pattern=r"^reserve:time:.+$")
            ],
            ReserveStates.CHOOSE_DURATION: [
                CallbackQueryHandler(choose_duration, pattern=r"^reserve:duration:.+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_duration_custom),
            ],
            ReserveStates.CHOOSE_RAM: [
                CallbackQueryHandler(choose_ram, pattern=r"^reserve:ram:.+$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_ram_custom),
            ],
            ReserveStates.CONFIRM: [CallbackQueryHandler(confirm, pattern="^reserve:confirm$")],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="reserve_conversation",
        persistent=False,
    )
