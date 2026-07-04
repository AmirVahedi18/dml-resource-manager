from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from dml_bot.bot.auth import get_active_user, is_admin
from dml_bot.bot.keyboards import admin_menu_keyboard, main_menu_keyboard
from dml_bot.db.session import session_scope
from dml_bot.services import invite_service, user_service

HELP_TEXT_LEGACY = (
    "<b>DML Resource Manager</b>\n\n"
    "Use the buttons below to reserve a GPU, check the schedule, or manage your "
    "reservations and watches. You must follow the time slots you reserve — this is "
    "lab policy.\n\n"
    "Not registered yet? Ask the lab admin for an invite code, then send /start &lt;code&gt;."
)

NOT_REGISTERED_TEXT = (
    "You're not registered for the DML Resource Manager yet.\n"
    "Ask the lab admin for an invite code, then send /start <code> to register."
)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Main menu:") -> None:
    """Always sends a fresh message rather than editing, so it never clobbers a result message
    a handler just displayed (e.g. a reservation confirmation) by editing it out from under the user."""
    with session_scope() as session:
        admin = is_admin(session, update.effective_user.id, context)
    await update.effective_message.reply_text(text, reply_markup=main_menu_keyboard(admin))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    with session_scope() as session:
        user = get_active_user(session, telegram_id)
        if user is None and not is_admin(session, telegram_id, context):
            code = context.args[0] if context.args else None
            if code is None:
                await update.effective_message.reply_text(NOT_REGISTERED_TEXT)
                return
            try:
                invite_service.redeem_invite(session, code=code, telegram_id=telegram_id)
            except invite_service.InviteNotFoundError:
                await update.effective_message.reply_text(
                    "That invite code isn't valid. Ask the lab admin for a new one."
                )
                return
            except invite_service.InviteAlreadyUsedError:
                await update.effective_message.reply_text(
                    "That invite code has already been used. Ask the lab admin for a new one."
                )
                return
            except user_service.UserAlreadyExistsError:
                await update.effective_message.reply_text(
                    "You already have an account (it may be deactivated) -- ask the lab admin "
                    "to reactivate it instead of using an invite code."
                )
                return
            await update.effective_message.reply_text("✅ You're now registered!")

    await show_main_menu(update, context, "Welcome to the DML Resource Manager.")


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"Your Telegram ID is: <code>{update.effective_user.id}</code>",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(HELP_TEXT_LEGACY, parse_mode="HTML")
    else:
        await update.effective_message.reply_text(HELP_TEXT_LEGACY, parse_mode="HTML")


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await show_main_menu(update, context)
    return ConversationHandler.END


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    with session_scope() as session:
        allowed = is_admin(session, update.effective_user.id, context)
    if not allowed:
        await update.callback_query.edit_message_text("⛔ Admins only.")
        return
    await update.callback_query.edit_message_text("Admin panel:", reply_markup=admin_menu_keyboard())


async def cancel_wizard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data.clear()
    await show_main_menu(update, context, "Cancelled.")
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await show_main_menu(update, context, "Cancelled.")
    return ConversationHandler.END
