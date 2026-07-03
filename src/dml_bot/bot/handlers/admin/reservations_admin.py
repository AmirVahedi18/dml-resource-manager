from datetime import timedelta

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from dml_bot.bot.auth import require_admin
from dml_bot.bot.formatting import fmt_dt, fmt_ram
from dml_bot.bot.handlers.common import cancel_wizard_callback, show_main_menu
from dml_bot.bot.keyboards import confirm_keyboard, item_list_keyboard
from dml_bot.bot.states import AdminReservationsStates
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, usage_service
from dml_bot.utils.time_utils import utc_now


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    if not await require_admin(update, context):
        return ConversationHandler.END

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
        now = utc_now()
        reservations = usage_service.get_reservations_in_range(
            session, now, now + timedelta(days=regulation.booking_horizon_days)
        )
        reservations.sort(key=lambda r: r.start_time)
        items = [
            (
                r.id,
                f"{r.gpu.server.name} GPU{r.gpu.index_on_server} · {r.user.full_name} · {fmt_dt(r.start_time, tz_name)}",
            )
            for r in reservations
        ]

    if not items:
        await update.callback_query.edit_message_text("No upcoming reservations lab-wide.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    await update.callback_query.edit_message_text(
        "All upcoming reservations (tap to cancel one):",
        reply_markup=item_list_keyboard(items, "adminres:choose"),
    )
    return AdminReservationsStates.CHOOSE_RESERVATION


async def choose_reservation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    reservation_id = int(update.callback_query.data.split(":")[2])
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
    await update.callback_query.edit_message_text(text, reply_markup=confirm_keyboard("adminres"))
    return AdminReservationsStates.CONFIRM_CANCEL


async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    reservation_id = context.user_data["reservation_id"]

    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, reservation_id)
        reservation_service.cancel_reservation(session, reservation)

    context.user_data.clear()
    await update.callback_query.edit_message_text("✅ Reservation cancelled by admin.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def admin_reservations_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^admin:reservations$")],
        states={
            AdminReservationsStates.CHOOSE_RESERVATION: [
                CallbackQueryHandler(choose_reservation, pattern=r"^adminres:choose:\d+$")
            ],
            AdminReservationsStates.CONFIRM_CANCEL: [
                CallbackQueryHandler(confirm_cancel, pattern="^adminres:confirm$")
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="admin_reservations_conversation",
        persistent=False,
    )
