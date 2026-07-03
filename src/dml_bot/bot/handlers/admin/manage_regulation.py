from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from dml_bot.bot.auth import require_admin
from dml_bot.bot.handlers.common import cancel_wizard_callback, show_main_menu
from dml_bot.bot.keyboards import CANCEL_BUTTON, cancel_only_keyboard
from dml_bot.bot.states import AdminRegulationStates
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service

FIELD_LABELS = {
    "max_ram_per_reservation_mb": "Max RAM per reservation (MB)",
    "max_duration_hours": "Max duration per reservation (hours)",
    "booking_horizon_days": "Booking horizon (days ahead)",
    "min_reservation_slot_minutes": "Time slot size (minutes)",
    "max_active_reservations_per_user": "Max active reservations per user",
}


def _menu_keyboard(regulation) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{label}: {getattr(regulation, field)}", callback_data=f"adminreg:field:{field}")]
        for field, label in FIELD_LABELS.items()
    ]
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    if not await require_admin(update, context):
        return ConversationHandler.END

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
        markup = _menu_keyboard(regulation)
    await update.callback_query.edit_message_text(
        "Current regulation (tap a field to edit):", reply_markup=markup
    )
    return AdminRegulationStates.MENU


async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    field = update.callback_query.data.split(":", 2)[2]
    context.user_data["field"] = field

    await update.callback_query.edit_message_text(
        f"Send the new value for '{FIELD_LABELS[field]}':", reply_markup=cancel_only_keyboard()
    )
    return AdminRegulationStates.EDIT_VALUE


async def receive_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data["field"]
    try:
        value = int(update.message.text.strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a positive whole number.")
        return AdminRegulationStates.EDIT_VALUE

    with session_scope() as session:
        regulation_service.update_regulation(session, update.effective_user.id, **{field: value})

    context.user_data.clear()
    await update.message.reply_text(f"✅ {FIELD_LABELS[field]} updated to {value}.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def regulation_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^admin:regulation$")],
        states={
            AdminRegulationStates.MENU: [
                CallbackQueryHandler(choose_field, pattern=r"^adminreg:field:\w+$")
            ],
            AdminRegulationStates.EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_value)
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="admin_regulation_conversation",
        persistent=False,
    )
