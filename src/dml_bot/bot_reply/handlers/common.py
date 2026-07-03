from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from dml_bot.bot.auth import get_active_user, is_admin
from dml_bot.bot.handlers.common import myid_command  # noqa: F401 -- interface-agnostic, reused as-is
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.keyboards import (
    BACK,
    MAIN_MENU,
    MORE_AMOUNTS,
    NEXT_PAGE,
    PREV_PAGE,
    admin_menu_keyboard,
    main_menu_keyboard,
    paginated_list_keyboard,
)
from dml_bot.db.session import session_scope

HELP_TEXT = (
    "<b>DML Resource Manager</b>\n\n"
    "Use the buttons below to reserve a GPU, check the schedule, or manage your "
    "reservations and watches. You must follow the time slots you reserve — this is "
    "lab policy.\n\n"
    "Not registered yet? Send /myid and give that number to the lab admin."
)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Main menu:") -> None:
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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT, parse_mode="HTML")


async def admin_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id, context):
        await update.effective_message.reply_text("⛔ Admins only.")
        return
    await update.effective_message.reply_text("Admin panel:", reply_markup=admin_menu_keyboard())


async def back_to_main_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_main_menu(update, context)


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await show_main_menu(update, context, "Cancelled.")
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await cancel_wizard(update, context)


async def handle_back_or_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE, render_page, back_render
) -> int | None:
    """Checks the incoming text against the controls every paginated list screen shares (Back /
    Main Menu / Prev / Next). Returns the next conversation state if it handled the text, or None
    if the caller should try resolving it as an item choice instead. `render_page` is an async,
    no-arg callback that re-renders the current step at the page now in
    `context.user_data["_page"]`. `back_render` is an async, no-arg callback that re-renders
    whatever the previous wizard step was -- these wizards are a fixed linear/tree sequence of
    screens (not a dynamic history), so each call site knows exactly which screen "back" means;
    for a wizard's very first step, pass `lambda: cancel_wizard(update, context)` since there's
    nothing to step back to."""
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        context.user_data.pop("_page", None)
        return await back_render()
    if text == PREV_PAGE:
        context.user_data["_page"] = max(0, context.user_data.get("_page", 0) - 1)
        return await render_page()
    if text == NEXT_PAGE:
        context.user_data["_page"] = context.user_data.get("_page", 0) + 1
        return await render_page()
    return None


async def render_paginated_step(update: Update, context: ContextTypes.DEFAULT_TYPE, items_key: str, prompt: str, state: int) -> int:
    """Sends the keyboard for `context.user_data[items_key]` at the current page, for a plain
    (non-preset) paginated list step. Callers store the full item list under `items_key` once,
    then call this to (re-)render whichever page is current."""
    items = context.user_data[items_key]
    page = context.user_data.get("_page", 0)
    markup = paginated_list_keyboard(context, items, page)
    await update.effective_message.reply_text(prompt, reply_markup=markup)
    return state


async def resolve_preset_or_more(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    mode_key: str,
    render_preset,
    render_fine,
    back_render,
):
    """Shared control flow for a preset-buttons screen with a "More amounts" escape hatch into a
    paginated finer-grained list (keyboards.preset_keyboard / paginated_list_keyboard). Returns
    `(state, value)`: if `state` is not None the caller should return it immediately (a fresh
    screen render or a retry prompt); otherwise `value` is the resolved choice. `back_render` is
    only used for Back pressed from the *preset* screen (the previous wizard step) -- Back from
    the "fine" sub-list just drops back to presets, since that's a step within this same screen,
    not the previous wizard step."""
    text = update.effective_message.text
    mode = context.user_data.get(mode_key, "preset")

    if mode == "preset" and text == MORE_AMOUNTS:
        context.user_data[mode_key] = "fine"
        context.user_data["_page"] = 0
        return await render_fine(), None

    if mode == "fine" and text == BACK:
        context.user_data[mode_key] = "preset"
        context.user_data.pop("_page", None)
        return await render_preset(), None

    render_current = render_preset if mode == "preset" else render_fine
    paged = await handle_back_or_cancel(update, context, render_current, back_render)
    if paged is not None:
        return paged, None

    value = resolve_choice(context, text)
    if value is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return await render_current(), None
    return None, value
