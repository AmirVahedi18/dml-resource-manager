from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import fmt_dt
from dml_bot.bot.handlers.common import cancel_wizard_callback, show_main_menu
from dml_bot.bot.keyboards import confirm_keyboard, item_list_keyboard
from dml_bot.bot.states import CancelStates
from dml_bot.db.session import session_scope
from dml_bot.services import reservation_service


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    tz_name = context.application.bot_data["config"].bot.timezone

    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            await update.callback_query.edit_message_text("You're not registered yet.")
            return ConversationHandler.END
        reservations = reservation_service.list_active_reservations_for_user(session, user.id)
        items = [
            (r.id, f"{r.gpu.server.name} GPU{r.gpu.index_on_server} · {fmt_dt(r.start_time, tz_name)}")
            for r in reservations
        ]

    if not items:
        await update.callback_query.edit_message_text("You have no upcoming reservations.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    await update.callback_query.edit_message_text(
        "Choose a reservation to cancel:", reply_markup=item_list_keyboard(items, "cancelres:choose")
    )
    return CancelStates.CHOOSE_RESERVATION


async def choose_reservation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    reservation_id = int(update.callback_query.data.split(":")[2])
    context.user_data["reservation_id"] = reservation_id

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, reservation_id)
        text = (
            f"Cancel this reservation?\n\n"
            f"{reservation.gpu.server.name} GPU{reservation.gpu.index_on_server}\n"
            f"{fmt_dt(reservation.start_time, tz_name)} → {fmt_dt(reservation.end_time, tz_name)}"
        )
    await update.callback_query.edit_message_text(text, reply_markup=confirm_keyboard("cancelres"))
    return CancelStates.CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    reservation_id = context.user_data["reservation_id"]

    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, reservation_id)
        reservation_service.cancel_reservation(session, reservation)

    context.user_data.clear()
    await update.callback_query.edit_message_text("✅ Reservation cancelled.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def cancel_reservation_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^menu:my_reservations$")],
        states={
            CancelStates.CHOOSE_RESERVATION: [
                CallbackQueryHandler(choose_reservation, pattern=r"^cancelres:choose:\d+$")
            ],
            CancelStates.CONFIRM: [CallbackQueryHandler(confirm, pattern="^cancelres:confirm$")],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="cancel_reservation_conversation",
        persistent=False,
    )
