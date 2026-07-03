from datetime import timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import require_admin
from dml_bot.bot.formatting import fmt_dt, fmt_ram
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import (
    cancel_wizard,
    handle_back_or_cancel,
    render_paginated_step,
    show_main_menu,
)
from dml_bot.bot_reply.keyboards import BACK, CONFIRM, MAIN_MENU, confirm_keyboard
from dml_bot.bot_reply.states import AdminReservationsStates
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, usage_service
from dml_bot.utils.time_utils import utc_now

MENU_BUTTON = "📋 All Reservations"


def _reservation_items(session, tz_name: str) -> list[tuple[str, int]]:
    regulation = regulation_service.get_regulation(session)
    now = utc_now()
    reservations = usage_service.get_reservations_in_range(session, now, now + timedelta(days=regulation.booking_horizon_days))
    reservations.sort(key=lambda r: r.start_time)
    return [
        (f"{r.gpu.server.name} GPU{r.gpu.index_on_server} · {r.user.full_name} · {fmt_dt(r.start_time, tz_name)}", r.id)
        for r in reservations
    ]


async def _render_list_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_paginated_step(
        update, context, "_reservation_items", "All upcoming reservations (tap to cancel one):", AdminReservationsStates.CHOOSE_RESERVATION
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_admin(update, context):
        return ConversationHandler.END

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        items = _reservation_items(session, tz_name)

    if not items:
        await update.effective_message.reply_text("No upcoming reservations lab-wide.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["_reservation_items"] = items
    context.user_data["_page"] = 0
    return await _render_list_step(update, context)


async def choose_reservation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_list_step(update, context), lambda: cancel_wizard(update, context)
    )
    if result is not None:
        return result

    reservation_id = resolve_choice(context, update.effective_message.text)
    if reservation_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminReservationsStates.CHOOSE_RESERVATION
    context.user_data["reservation_id"] = reservation_id

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, reservation_id)
        text = (
            f"Cancel this reservation (admin override)?\n\n"
            f"{reservation.gpu.server.name} GPU{reservation.gpu.index_on_server}\n"
            f"Student: {reservation.user.full_name}\n"
            f"{fmt_dt(reservation.start_time, tz_name)} → {fmt_dt(reservation.end_time, tz_name)}\n"
            f"RAM: {fmt_ram(reservation.ram_mb)}"
        )
    await update.effective_message.reply_text(text, reply_markup=confirm_keyboard())
    return AdminReservationsStates.CONFIRM_CANCEL


async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_list_step(update, context)
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminReservationsStates.CONFIRM_CANCEL

    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, context.user_data["reservation_id"])
        reservation_service.cancel_reservation(session, reservation)

    context.user_data.clear()
    await update.effective_message.reply_text("✅ Reservation cancelled by admin.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def admin_reservations_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            AdminReservationsStates.CHOOSE_RESERVATION: [MessageHandler(text_filter, choose_reservation)],
            AdminReservationsStates.CONFIRM_CANCEL: [MessageHandler(text_filter, confirm_cancel)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_admin_reservations_conversation",
        persistent=False,
    )
