from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from dml_bot.bot.auth import get_active_user, is_admin
from dml_bot.bot.keyboards import admin_menu_keyboard, main_menu_keyboard
from dml_bot.db.session import session_scope

HELP_TEXT = (
    "<b>DML Resource Manager</b>\n\n"
    "Use the buttons below to reserve a GPU, check the schedule, or manage your "
    "reservations and watches. You must follow the time slots you reserve — this is "
    "lab policy.\n\n"
    "Not registered yet? Send /myid and give that number to the lab admin."
)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Main menu:") -> None:
    """Always sends a fresh message rather than editing, so it never clobbers a result message
    a handler just displayed (e.g. a reservation confirmation) by editing it out from under the user."""
    admin = is_admin(update.effective_user.id, context)
    await update.effective_message.reply_text(text, reply_markup=main_menu_keyboard(admin))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None and not is_admin(update.effective_user.id, context):
            await update.effective_message.reply_text(
                "You're not registered for the DML Resource Manager yet.\n"
                "Send /myid and give that number to the lab admin to get registered."
            )
            return
    await show_main_menu(update, context, "Welcome to the DML Resource Manager.")


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"Your Telegram ID is: <code>{update.effective_user.id}</code>",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(HELP_TEXT, parse_mode="HTML")
    else:
        await update.effective_message.reply_text(HELP_TEXT, parse_mode="HTML")


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await show_main_menu(update, context)
    return ConversationHandler.END


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    if not is_admin(update.effective_user.id, context):
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
