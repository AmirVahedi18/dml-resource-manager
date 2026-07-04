from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import require_admin
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import (
    cancel_wizard,
    cancel_wizard_to_admin,
    handle_back_or_cancel,
    show_main_menu,
)
from dml_bot.bot_reply.keyboards import (
    BACK,
    CONFIRM,
    DONE,
    MAIN_MENU,
    action_keyboard,
    cancel_only_keyboard,
    confirm_keyboard,
    paginated_list_keyboard,
    toggle_list_keyboard,
)
from dml_bot.bot_reply.states import AdminUserStates
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import server_access_service, server_service, user_service

MENU_BUTTON = "👤 Manage Users"
ADD_USER = "➕ Add User"


def _server_toggle_items(session) -> list[tuple[str, int]]:
    return [(server.name, server.id) for server in server_service.list_servers(session)]


def _user_items(session) -> list[tuple[str, int]]:
    items = []
    for u in user_service.list_users(session, active_only=False):
        flags = ("✅" if u.is_active else "🚫") + (" ⭐" if u.can_use_multiple_gpus else "")
        items.append((f"{u.full_name} {flags}", u.id))
    return items


async def _render_list_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("_viewing_user_id", None)
    items = context.user_data.get("_user_items", [])
    page = context.user_data.get("_page", 0)
    grid = context.application.bot_data["config"].list_grids.user_list
    markup = paginated_list_keyboard(
        context, items, page, extra_rows=[[ADD_USER]], columns=grid.columns, rows=grid.rows
    )
    text = "Registered users (✅ active, 🚫 inactive, ⭐ privileged):" if items else "No users registered yet."
    await update.effective_message.reply_text(text, reply_markup=markup)
    return AdminUserStates.MENU


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_admin(update, context):
        return ConversationHandler.END

    with session_scope() as session:
        items = _user_items(session)
    context.user_data.clear()
    context.user_data["_user_items"] = items
    context.user_data["_page"] = 0
    return await _render_list_step(update, context)


async def _show_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> int:
    context.user_data["_viewing_user_id"] = user_id
    with session_scope() as session:
        user = session.get(User, user_id)
        text_out = (
            f"<b>{user.full_name}</b>\n"
            f"Telegram ID: {user.telegram_id}\n"
            f"Status: {'active' if user.is_active else 'inactive'}\n"
            f"Multi-GPU privilege: {'yes' if user.can_use_multiple_gpus else 'no'}"
        )
        actions = [
            ("🚫 Deactivate" if user.is_active else "✅ Activate", ("toggle_active", user_id)),
            (
                "⭐ Revoke multi-GPU" if user.can_use_multiple_gpus else "⭐ Grant multi-GPU",
                ("toggle_privilege", user_id),
            ),
            ("✏️ Rename", ("rename", user_id)),
            ("🔐 Server Access", ("access", user_id)),
            ("🗑 Remove", ("delete", user_id)),
        ]
    markup = action_keyboard(context, actions)
    await update.effective_message.reply_text(text_out, reply_markup=markup, parse_mode="HTML")
    return AdminUserStates.MENU


async def menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == ADD_USER:
        await update.effective_message.reply_text(
            "Send the new student's Telegram numeric ID (ask them to send /myid to this bot):",
            reply_markup=cancel_only_keyboard(),
        )
        return AdminUserStates.ADD_TELEGRAM_ID

    viewing_user_id = context.user_data.get("_viewing_user_id")
    back_render = (
        (lambda: _render_list_step(update, context))
        if viewing_user_id is not None
        else (lambda: cancel_wizard_to_admin(update, context))
    )
    result = await handle_back_or_cancel(update, context, lambda: _render_list_step(update, context), back_render)
    if result is not None:
        return result

    choice = resolve_choice(context, text)
    if choice is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminUserStates.MENU

    if isinstance(choice, tuple):
        action, user_id = choice
        if action == "rename":
            context.user_data["_viewing_user_id"] = user_id
            await update.effective_message.reply_text(
                "Send the new full name:", reply_markup=cancel_only_keyboard()
            )
            return AdminUserStates.RENAME
        if action == "delete":
            context.user_data["_viewing_user_id"] = user_id
            with session_scope() as session:
                name = session.get(User, user_id).full_name
            await update.effective_message.reply_text(
                f"⚠️ Permanently delete {name} and all their reservations/watches? This cannot be undone.",
                reply_markup=confirm_keyboard(),
            )
            return AdminUserStates.CONFIRM_DELETE
        if action == "access":
            context.user_data["_viewing_user_id"] = user_id
            with session_scope() as session:
                items = _server_toggle_items(session)
                selected = server_access_service.list_accessible_server_ids(session, user_id)
            if not items:
                await update.effective_message.reply_text("No servers exist yet -- add one first (🖥 Manage Servers).")
                return await _show_user_detail(update, context, user_id)
            context.user_data["_server_toggle_items"] = items
            context.user_data["_edit_access_ids"] = selected
            return await _render_edit_access_step(update, context)

        with session_scope() as session:
            user = session.get(User, user_id)
            if action == "toggle_active":
                user_service.set_active(session, user, not user.is_active)
            else:
                user_service.set_privilege(session, user, not user.can_use_multiple_gpus)
            items = _user_items(session)
        context.user_data["_user_items"] = items
        context.user_data["_page"] = 0
        return await _render_list_step(update, context)

    return await _show_user_detail(update, context, choice)


async def receive_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _show_user_detail(update, context, context.user_data["_viewing_user_id"])
    if not text:
        await update.effective_message.reply_text("Please send a non-empty name.")
        return AdminUserStates.RENAME

    with session_scope() as session:
        user = session.get(User, context.user_data["_viewing_user_id"])
        user_service.rename_user(session, user, text)
        items = _user_items(session)
    context.user_data["_user_items"] = items
    context.user_data["_page"] = 0
    await update.effective_message.reply_text(f"✅ Renamed to {text}.")
    return await _render_list_step(update, context)


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _show_user_detail(update, context, context.user_data["_viewing_user_id"])
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminUserStates.CONFIRM_DELETE

    with session_scope() as session:
        user = session.get(User, context.user_data["_viewing_user_id"])
        name = user.full_name
        user_service.delete_user(session, user)
        items = _user_items(session)
    context.user_data["_user_items"] = items
    context.user_data["_page"] = 0
    await update.effective_message.reply_text(f"🗑 Deleted {name}.")
    return await _render_list_step(update, context)


async def _render_edit_access_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    items = context.user_data["_server_toggle_items"]
    selected = context.user_data.get("_edit_access_ids", set())
    markup = toggle_list_keyboard(context, items, selected)
    await update.effective_message.reply_text(
        "Toggle this student's server access, then tap Done:", reply_markup=markup
    )
    return AdminUserStates.EDIT_SERVER_ACCESS


async def choose_edit_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    user_id = context.user_data["_viewing_user_id"]
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _show_user_detail(update, context, user_id)
    if text == DONE:
        selected = context.user_data.get("_edit_access_ids", set())
        with session_scope() as session:
            server_access_service.set_access(session, user_id, selected)
        await update.effective_message.reply_text(f"✅ Access updated ({len(selected)} server(s) granted).")
        return await _show_user_detail(update, context, user_id)

    choice = resolve_choice(context, text)
    if choice is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminUserStates.EDIT_SERVER_ACCESS

    selected = context.user_data.setdefault("_edit_access_ids", set())
    if choice in selected:
        selected.discard(choice)
    else:
        selected.add(choice)
    return await _render_edit_access_step(update, context)


async def receive_telegram_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_list_step(update, context)
    try:
        telegram_id = int(text)
    except ValueError:
        await update.effective_message.reply_text("Please send a numeric Telegram ID.")
        return AdminUserStates.ADD_TELEGRAM_ID

    with session_scope() as session:
        if user_service.get_user_by_telegram_id(session, telegram_id) is not None:
            await update.effective_message.reply_text("A user with that Telegram ID is already registered.")
            return AdminUserStates.ADD_TELEGRAM_ID

    context.user_data["new_telegram_id"] = telegram_id
    await update.effective_message.reply_text("Now send their full name:", reply_markup=cancel_only_keyboard())
    return AdminUserStates.ADD_FULL_NAME


async def receive_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = update.effective_message.text.strip()
    if full_name == MAIN_MENU:
        return await cancel_wizard(update, context)
    if full_name == BACK:
        await update.effective_message.reply_text(
            "Send the new student's Telegram numeric ID (ask them to send /myid to this bot):",
            reply_markup=cancel_only_keyboard(),
        )
        return AdminUserStates.ADD_TELEGRAM_ID
    if not full_name:
        await update.effective_message.reply_text("Please send a non-empty name.")
        return AdminUserStates.ADD_FULL_NAME

    context.user_data["new_full_name"] = full_name
    with session_scope() as session:
        items = _server_toggle_items(session)
    if not items:
        await update.effective_message.reply_text(
            "No servers exist yet -- add one first (🖥 Manage Servers), then add this user."
        )
        context.user_data.clear()
        await show_main_menu(update, context)
        return ConversationHandler.END

    context.user_data["_server_toggle_items"] = items
    context.user_data["_new_access_ids"] = set()
    return await _render_new_user_access_step(update, context)


async def _render_new_user_access_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    items = context.user_data["_server_toggle_items"]
    selected = context.user_data.get("_new_access_ids", set())
    markup = toggle_list_keyboard(context, items, selected)
    await update.effective_message.reply_text(
        "Select which server(s) this student can access, then tap Done (at least one required):",
        reply_markup=markup,
    )
    return AdminUserStates.ADD_SERVER_ACCESS


async def choose_new_user_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        await update.effective_message.reply_text("Now send their full name:", reply_markup=cancel_only_keyboard())
        return AdminUserStates.ADD_FULL_NAME
    if text == DONE:
        selected = context.user_data.get("_new_access_ids", set())
        if not selected:
            await update.effective_message.reply_text("Select at least one server before continuing.")
            return await _render_new_user_access_step(update, context)

        telegram_id = context.user_data["new_telegram_id"]
        full_name = context.user_data["new_full_name"]
        with session_scope() as session:
            user = user_service.register_user(session, telegram_id=telegram_id, full_name=full_name)
            server_access_service.set_access(session, user.id, selected)

        context.user_data.clear()
        await update.effective_message.reply_text(
            f"✅ Registered {full_name} (Telegram ID {telegram_id}) with access to {len(selected)} server(s)."
        )
        await show_main_menu(update, context)
        return ConversationHandler.END

    choice = resolve_choice(context, text)
    if choice is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminUserStates.ADD_SERVER_ACCESS

    selected = context.user_data.setdefault("_new_access_ids", set())
    if choice in selected:
        selected.discard(choice)
    else:
        selected.add(choice)
    return await _render_new_user_access_step(update, context)


def users_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            AdminUserStates.MENU: [MessageHandler(text_filter, menu_choice)],
            AdminUserStates.ADD_TELEGRAM_ID: [MessageHandler(text_filter, receive_telegram_id)],
            AdminUserStates.ADD_FULL_NAME: [MessageHandler(text_filter, receive_full_name)],
            AdminUserStates.ADD_SERVER_ACCESS: [MessageHandler(text_filter, choose_new_user_access)],
            AdminUserStates.RENAME: [MessageHandler(text_filter, receive_rename)],
            AdminUserStates.CONFIRM_DELETE: [MessageHandler(text_filter, confirm_delete)],
            AdminUserStates.EDIT_SERVER_ACCESS: [MessageHandler(text_filter, choose_edit_access)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_admin_users_conversation",
        persistent=False,
    )
