from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from dml_bot.bot.auth import is_bootstrap_admin, require_admin
from dml_bot.bot.handlers.common import cancel_wizard_callback, show_main_menu
from dml_bot.bot.keyboards import CANCEL_BUTTON, cancel_only_keyboard
from dml_bot.bot.states import AdminUserStates
from dml_bot.db.models.invite_code import InviteCode
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import invite_service, user_service


def _render_list(session) -> tuple[str, InlineKeyboardMarkup]:
    users = user_service.list_users(session, active_only=False)
    invites = invite_service.list_pending_invites(session)
    rows = []
    for u in users:
        flags = (
            ("✅" if u.is_active else "🚫")
            + (" ⭐" if u.can_use_multiple_gpus else "")
            + (" 🛡" if u.is_admin else "")
        )
        rows.append([InlineKeyboardButton(f"{u.full_name} {flags}", callback_data=f"adminusers:select:{u.id}")])
    for inv in invites:
        rows.append(
            [InlineKeyboardButton(
                f"📨 {inv.full_name} ({inv.code}) 🗑", callback_data=f"adminusers:revokeinvite:{inv.id}"
            )]
        )
    rows.append([InlineKeyboardButton("➕ Add User", callback_data="adminusers:add")])
    rows.append([CANCEL_BUTTON])
    if users or invites:
        text = (
            "Registered users (✅ active, 🚫 inactive, ⭐ privileged, 🛡 admin); "
            "📨 = pending invite, tap to revoke:"
        )
    else:
        text = "No users registered yet."
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
            f"Multi-GPU privilege: {'yes' if user.can_use_multiple_gpus else 'no'}\n"
            f"Admin role: {'yes' if user.is_admin else 'no'}"
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
    ]
    if is_bootstrap_admin(update.effective_user.id, context):
        rows.append([InlineKeyboardButton(
            "🛡 Revoke admin" if user.is_admin else "🛡 Grant admin",
            callback_data=f"adminusers:toggleadmin:{user_id}",
        )])
    rows.append([CANCEL_BUTTON])
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


async def toggle_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_bootstrap_admin(update.effective_user.id, context):
        await update.callback_query.answer("⛔ Only a bootstrap admin can do that.", show_alert=True)
        return AdminUserStates.MENU
    await update.callback_query.answer()
    user_id = int(update.callback_query.data.split(":")[2])
    with session_scope() as session:
        user = session.get(User, user_id)
        user_service.set_admin(session, user, not user.is_admin)
        text, markup = _render_list(session)
    await update.callback_query.edit_message_text(text, reply_markup=markup)
    return AdminUserStates.MENU


async def ask_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Send the new student's full name:",
        reply_markup=cancel_only_keyboard(),
    )
    return AdminUserStates.ADD_FULL_NAME


async def receive_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.message.text.strip()
    if not full_name:
        await update.message.reply_text("Please send a non-empty name.")
        return AdminUserStates.ADD_FULL_NAME

    with session_scope() as session:
        invite = invite_service.create_invite(session, full_name=full_name)
        code = invite.code

    context.user_data.clear()
    await update.message.reply_text(
        f"✅ Invite created for {full_name}. Give them this code and ask them to send:\n\n"
        f"<code>/start {code}</code>\n\n"
        "to this bot to finish registering.",
        parse_mode="HTML",
    )
    await show_main_menu(update, context)
    return ConversationHandler.END


async def revoke_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    invite_id = int(update.callback_query.data.split(":")[2])
    with session_scope() as session:
        invite = session.get(InviteCode, invite_id)
        if invite is not None:
            invite_service.revoke_invite(session, invite)
        text, markup = _render_list(session)
    await update.callback_query.edit_message_text(text, reply_markup=markup)
    return AdminUserStates.MENU


def users_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^admin:users$")],
        states={
            AdminUserStates.MENU: [
                CallbackQueryHandler(ask_full_name, pattern="^adminusers:add$"),
                CallbackQueryHandler(select_user, pattern=r"^adminusers:select:\d+$"),
                CallbackQueryHandler(toggle_active, pattern=r"^adminusers:toggleactive:\d+$"),
                CallbackQueryHandler(toggle_privilege, pattern=r"^adminusers:togglepriv:\d+$"),
                CallbackQueryHandler(toggle_admin, pattern=r"^adminusers:toggleadmin:\d+$"),
                CallbackQueryHandler(revoke_invite, pattern=r"^adminusers:revokeinvite:\d+$"),
            ],
            AdminUserStates.ADD_FULL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_full_name)
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="admin_users_conversation",
        persistent=False,
    )
