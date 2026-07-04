from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import fmt_dt, fmt_ram
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import (
    cancel_wizard,
    handle_back_or_cancel,
    render_paginated_step,
    show_main_menu,
)
from dml_bot.bot_reply.keyboards import BACK, CONFIRM, MAIN_MENU, confirm_keyboard
from dml_bot.bot_reply.states import CancelStates
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service

MENU_BUTTON = "🗂 My Reservations"


async def _reservation_items(session, telegram_id: int, tz_name: str) -> list[tuple[str, int]]:
    user = get_active_user(session, telegram_id)
    if user is None:
        return []
    reservations = reservation_service.list_active_reservations_for_user(session, user.id)
    return [
        (
            f"{r.gpu.server.name} GPU{r.gpu.index_on_server} · "
            f"{fmt_dt(r.start_time, tz_name)} → {fmt_dt(r.end_time, tz_name)} · {fmt_ram(r.ram_mb)}",
            r.id,
        )
        for r in reservations
    ]


async def _render_list_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_paginated_step(
        update, context, "_reservation_items", "Choose a reservation to cancel:", CancelStates.CHOOSE_RESERVATION
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            await update.effective_message.reply_text("You're not registered yet.")
            return ConversationHandler.END
        items = await _reservation_items(session, update.effective_user.id, tz_name)

    if not items:
        await update.effective_message.reply_text("You have no upcoming reservations.")
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
        return CancelStates.CHOOSE_RESERVATION
    context.user_data["reservation_id"] = reservation_id

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, reservation_id)
        text = (
            f"Cancel this reservation?\n\n"
            f"{reservation.gpu.server.name} GPU{reservation.gpu.index_on_server}\n"
            f"{fmt_dt(reservation.start_time, tz_name)} → {fmt_dt(reservation.end_time, tz_name)}\n"
            f"RAM: {fmt_ram(reservation.ram_mb)}"
        )
    await update.effective_message.reply_text(text, reply_markup=confirm_keyboard())
    return CancelStates.CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_list_step(update, context)
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return CancelStates.CONFIRM

    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, context.user_data["reservation_id"])
        regulation = regulation_service.get_regulation(session)
        try:
            reservation_service.assert_cancellable(reservation, regulation)
            reservation_service.cancel_reservation(session, reservation)
        except reservation_service.ReservationError as exc:
            await update.effective_message.reply_text(f"Could not cancel reservation: {exc}")
            context.user_data.clear()
            return ConversationHandler.END

    context.user_data.clear()
    await update.effective_message.reply_text("✅ Reservation cancelled.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def cancel_reservation_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            CancelStates.CHOOSE_RESERVATION: [MessageHandler(text_filter, choose_reservation)],
            CancelStates.CONFIRM: [MessageHandler(text_filter, confirm)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_cancel_reservation_conversation",
        persistent=False,
    )
