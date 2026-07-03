from datetime import timedelta

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import fmt_ram, fmt_dt
from dml_bot.bot.handlers.common import cancel_wizard_callback, show_main_menu
from dml_bot.bot.keyboards import gpu_list_keyboard, range_picker_keyboard, server_list_keyboard
from dml_bot.bot.states import ScheduleStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, server_service
from dml_bot.utils.time_utils import local_day_range_utc, to_local_label, utc_now

RANGE_LABELS = {"today": "today", "week": "the next 7 days", "month": "the next 30 days", "horizon": "the full booking horizon"}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            await update.callback_query.edit_message_text("You're not registered yet.")
            return ConversationHandler.END
        servers = server_service.list_servers(session)

    if not servers:
        await update.callback_query.edit_message_text("No servers are configured yet.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.callback_query.edit_message_text(
        "Choose a server:", reply_markup=server_list_keyboard(servers, "schedule")
    )
    return ScheduleStates.CHOOSE_SERVER


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
        f"Server: {server.name}\nChoose a GPU:", reply_markup=gpu_list_keyboard(gpus, "schedule")
    )
    return ScheduleStates.CHOOSE_GPU


async def choose_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    gpu_id = int(update.callback_query.data.split(":")[2])
    context.user_data["gpu_id"] = gpu_id

    await update.callback_query.edit_message_text(
        "Choose a date range:", reply_markup=range_picker_keyboard("schedule")
    )
    return ScheduleStates.CHOOSE_RANGE


async def choose_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    range_key = update.callback_query.data.split(":")[2]
    tz_name = context.application.bot_data["config"].bot.timezone

    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
        server = session.get(Server, context.user_data["server_id"])
        regulation = regulation_service.get_regulation(session)

        now = utc_now()
        if range_key == "today":
            range_start, range_end = local_day_range_utc(now.date(), tz_name)
        elif range_key == "week":
            range_start, range_end = now, now + timedelta(days=7)
        elif range_key == "month":
            range_start, range_end = now, now + timedelta(days=30)
        else:
            range_start, range_end = now, now + timedelta(days=regulation.booking_horizon_days)

        reservations = reservation_service.list_reservations_for_gpu(session, gpu.id, range_start, range_end)
        reservations.sort(key=lambda r: r.start_time)
        lines = [
            f"{to_local_label(r.start_time, tz_name)}–{to_local_label(r.end_time, tz_name)} "
            f"· {r.user.full_name} · {fmt_ram(r.ram_mb)}"
            for r in reservations
        ]

    header = f"<b>{server.name} GPU{gpu.index_on_server}</b> — {RANGE_LABELS[range_key]}\n\n"
    body = "\n".join(lines) if lines else "Fully free in this range."
    text = header + body + f"\n\n(times shown in {tz_name})"

    context.user_data.clear()
    await update.callback_query.edit_message_text(text, parse_mode="HTML")
    await show_main_menu(update, context)
    return ConversationHandler.END


def schedule_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^menu:schedule$")],
        states={
            ScheduleStates.CHOOSE_SERVER: [CallbackQueryHandler(choose_server, pattern=r"^schedule:server:\d+$")],
            ScheduleStates.CHOOSE_GPU: [CallbackQueryHandler(choose_gpu, pattern=r"^schedule:gpu:\d+$")],
            ScheduleStates.CHOOSE_RANGE: [CallbackQueryHandler(choose_range, pattern=r"^schedule:range:\w+$")],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="schedule_conversation",
        persistent=False,
    )
