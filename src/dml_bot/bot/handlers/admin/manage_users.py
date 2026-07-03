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
from dml_bot.bot.states import AdminUserStates
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import user_service


def _render_list(session) -> tuple[str, InlineKeyboardMarkup]:
    users = user_service.list_users(session, active_only=False)
    rows = []
    for u in users:
        flags = ("✅" if u.is_active else "🚫") + (" ⭐" if u.can_use_multiple_gpus else "")
        rows.append([InlineKeyboardButton(f"{u.full_name} {flags}", callback_data=f"adminusers:select:{u.id}")])
    rows.append([InlineKeyboardButton("➕ Add User", callback_data="adminusers:add")])
    rows.append([CANCEL_BUTTON])
    text = "Registered users (✅ active, 🚫 inactive, ⭐ privileged):" if users else "No users registered yet."
    return text, InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    if not await require_admin(update, context):
        return ConversationHandler.END

    with session_scope() as session:
        text, markup = _render_list(session)
    await update.callback_query.edit_message_text(text, reply_markup=markup)
    return AdminUserStates.MENU


async def select_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    user_id = int(update.callback_query.data.split(":")[2])

    with session_scope() as session:
        user = session.get(User, user_id)
        text = (
            f"<b>{user.full_name}</b>\n"
            f"Telegram ID: {user.telegram_id}\n"
            f"Status: {'active' if user.is_active else 'inactive'}\n"
            f"Multi-GPU privilege: {'yes' if user.can_use_multiple_gpus else 'no'}"
        )
    rows = [
        [InlineKeyboardButton(
            "🚫 Deactivate" if user.is_active else "✅ Activate",
            callback_data=f"adminusers:toggleactive:{user_id}",
        )],
        [InlineKeyboardButton(
            "⭐ Revoke multi-GPU" if user.can_use_multiple_gpus else "⭐ Grant multi-GPU",
            callback_data=f"adminusers:togglepriv:{user_id}",
        )],
        [CANCEL_BUTTON],
    ]
    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML"
    )
    return AdminUserStates.MENU


async def toggle_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    user_id = int(update.callback_query.data.split(":")[2])
    with session_scope() as session:
        user = session.get(User, user_id)
        user_service.set_active(session, user, not user.is_active)
        text, markup = _render_list(session)
    await update.callback_query.edit_message_text(text, reply_markup=markup)
    return AdminUserStates.MENU


async def toggle_privilege(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    user_id = int(update.callback_query.data.split(":")[2])
    with session_scope() as session:
        user = session.get(User, user_id)
        user_service.set_privilege(session, user, not user.can_use_multiple_gpus)
        text, markup = _render_list(session)
    await update.callback_query.edit_message_text(text, reply_markup=markup)
    return AdminUserStates.MENU


async def ask_telegram_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Send the new student's Telegram numeric ID (ask them to send /myid to this bot):",
        reply_markup=cancel_only_keyboard(),
    )
    return AdminUserStates.ADD_TELEGRAM_ID


async def receive_telegram_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        telegram_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please send a numeric Telegram ID.")
        return AdminUserStates.ADD_TELEGRAM_ID

    with session_scope() as session:
        if user_service.get_user_by_telegram_id(session, telegram_id) is not None:
            await update.message.reply_text("A user with that Telegram ID is already registered.")
            return AdminUserStates.ADD_TELEGRAM_ID

    context.user_data["new_telegram_id"] = telegram_id
    await update.message.reply_text("Now send their full name:")
    return AdminUserStates.ADD_FULL_NAME


async def receive_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.text.strip()
    if not full_name:
        await update.message.reply_text("Please send a non-empty name.")
        return AdminUserStates.ADD_FULL_NAME

    telegram_id = context.user_data["new_telegram_id"]
    with session_scope() as session:
        user_service.register_user(session, telegram_id=telegram_id, full_name=full_name)

    context.user_data.clear()
    await update.message.reply_text(f"✅ Registered {full_name} (Telegram ID {telegram_id}).")
    await show_main_menu(update, context)
    return ConversationHandler.END


def users_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^admin:users$")],
        states={
            AdminUserStates.MENU: [
                CallbackQueryHandler(ask_telegram_id, pattern="^adminusers:add$"),
                CallbackQueryHandler(select_user, pattern=r"^adminusers:select:\d+$"),
                CallbackQueryHandler(toggle_active, pattern=r"^adminusers:toggleactive:\d+$"),
                CallbackQueryHandler(toggle_privilege, pattern=r"^adminusers:togglepriv:\d+$"),
            ],
            AdminUserStates.ADD_TELEGRAM_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_telegram_id)
            ],
            AdminUserStates.ADD_FULL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_full_name)
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="admin_users_conversation",
        persistent=False,
    )
