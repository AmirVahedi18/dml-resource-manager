from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import require_admin
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import cancel_wizard, show_main_menu
from dml_bot.bot_reply.keyboards import BACK, MAIN_MENU, action_keyboard, cancel_only_keyboard
from dml_bot.bot_reply.states import AdminRegulationStates
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service

MENU_BUTTON = "⚖️ Regulation"

FIELD_LABELS = {
    "max_ram_per_reservation_mb": "Max RAM per reservation (MB)",
    "max_duration_hours": "Max duration per reservation (hours)",
    "booking_horizon_days": "Booking horizon (days ahead)",
    "min_reservation_slot_minutes": "Time slot size (minutes)",
    "max_active_reservations_per_user": "Max active reservations per user",
}


async def _render_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
        actions = [(f"{label}: {getattr(regulation, field)}", field) for field, label in FIELD_LABELS.items()]
    markup = action_keyboard(context, actions)
    await update.effective_message.reply_text("Current regulation (tap a field to edit):", reply_markup=markup)
    return AdminRegulationStates.MENU


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_admin(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    return await _render_menu(update, context)


async def choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text in (MAIN_MENU, BACK):  # this is the first screen, so Back also exits
        return await cancel_wizard(update, context)

    field = resolve_choice(context, text)
    if field is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return await _render_menu(update, context)

    context.user_data["field"] = field
    await update.effective_message.reply_text(
        f"Send the new value for '{FIELD_LABELS[field]}':", reply_markup=cancel_only_keyboard()
    )
    return AdminRegulationStates.EDIT_VALUE


async def receive_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_menu(update, context)

    field = context.user_data["field"]
    try:
        value = int(text)
        if value <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Please send a positive whole number.")
        return AdminRegulationStates.EDIT_VALUE

    with session_scope() as session:
        regulation_service.update_regulation(session, update.effective_user.id, **{field: value})

    context.user_data.clear()
    await update.effective_message.reply_text(f"✅ {FIELD_LABELS[field]} updated to {value}.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def regulation_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            AdminRegulationStates.MENU: [MessageHandler(text_filter, choose_field)],
            AdminRegulationStates.EDIT_VALUE: [MessageHandler(text_filter, receive_value)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_admin_regulation_conversation",
        persistent=False,
    )
