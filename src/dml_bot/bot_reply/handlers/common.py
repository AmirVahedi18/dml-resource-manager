from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from dml_bot.bot.auth import get_active_user, is_admin, is_bootstrap_admin
from dml_bot.bot_reply.keyboards import (
    BACK,
    MAIN_MENU,
    NEXT_PAGE,
    PAGE_SIZE,
    PREV_PAGE,
    admin_menu_keyboard,
    main_menu_keyboard,
    paginated_list_keyboard,
)
from dml_bot.db.session import session_scope
from dml_bot.services import invite_service, user_service

HELP_TEXT_STUDENT = (
    "<b>DML Resource Manager — Help</b>\n\n"
    "Every screen shows buttons below the message box — tap one instead of typing free text, "
    "except where a step explicitly asks you to type a number or value. Two buttons appear on "
    "almost every screen:\n"
    "• ◀ Back — goes back exactly one screen (not all the way to the start).\n"
    "• 🏠 Main Menu — exits whatever you're doing and returns to the main menu, from anywhere.\n\n"
    "Not registered yet? Ask the lab admin for an invite code, then send /start &lt;code&gt;.\n\n"
    "<b>📅 Reserve GPU</b> — book a GPU for a future time slot:\n"
    "1. Step 1/5 — pick a GPU from the list (only servers the admin gave you access to are shown).\n"
    "2. Step 2/5 — pick a date.\n"
    "3. Step 3/5 — pick a start time on that date.\n"
    "4. Step 4/5 — type a whole number of hours for the duration (capped by lab regulation).\n"
    "5. Step 5/5 — type a whole number (in the configured unit, e.g. GB) for the RAM you need, "
    "capped by how much is actually free on that GPU during your window and by the lab's "
    "per-reservation RAM limit.\n"
    "6. Review the summary and tap ✅ Confirm to book it, or ◀ Back to change the RAM/duration.\n\n"
    "<b>🗂 My Reservations</b> — cancel a reservation you made:\n"
    "1. Pick a reservation from the list (shows GPU, start → end time, and RAM).\n"
    "2. Review the details and tap ✅ Confirm to cancel it, or ◀ Back to pick a different one. If "
    "the lab requires advance notice to cancel, doing so too close to the start time is rejected "
    "with an explanation.\n\n"
    "<b>🗓 Schedule</b> — see how busy a GPU is:\n"
    "1. Step 1/2 — pick a GPU.\n"
    "2. Step 2/2 — pick a date range (Today, or a day-count preset, limited by the booking "
    "horizon).\n"
    "3. You get a text chart of RAM usage over that range, plus a list of the reservations in it.\n\n"
    "<b>🔔 Watches</b> — get notified (or auto-booked) when enough RAM frees up on a GPU:\n"
    "1. Your active watches are listed (tap one to cancel it), alongside ➕ New Watch.\n"
    "2. New Watch steps through the same screens as Reserve GPU: Step 1/5 pick a GPU (its "
    "availability chart is shown same as Reserve GPU), Step 2/5 pick a start date, Step 3/5 pick "
    "a start time, Step 4/5 type the window's duration in hours, Step 5/5 type the minimum RAM "
    "you need freed in that window -- then choose ✅ Yes, auto-book or 🔕 No, just notify.\n"
    "3. Just notify: you get a message here as soon as that much RAM becomes free in that window, "
    "and re-reserve it yourself -- first to act wins if others are watching the same capacity.\n"
    "4. Auto-book: the bot books the freed window for you automatically (from whenever it frees "
    "through your watch's window end, capped by the lab's max reservation duration) and you get a "
    "confirmation instead. If booking it fails for any reason (e.g. you're already at your active-"
    "reservation limit), you get a plain notification instead so you can still act manually."
)

HELP_TEXT_ADMIN = (
    "<b>🛠 Admin Panel</b> — additional options only admins see:\n\n"
    "<b>👤 Manage Users</b>:\n"
    "1. See all registered students (✅ active/🚫 inactive, (nGPU) = max concurrent GPUs if >1, 🛡 = admin), "
    "or tap ➕ Add User.\n"
    "2. Add User: type the student's full name, then pick at least one server to grant them "
    "access to -- you'll get a one-time invite code to send the student. They send /start "
    "&lt;code&gt; to this bot to finish registering themselves; no need to look up their "
    "Telegram ID first. Pending (not-yet-redeemed) invites are listed alongside registered "
    "students, with a 🗑 to revoke one.\n"
    "3. Tap a student to see actions: ✅/🚫 activate/deactivate, 🔢 set max concurrent GPUs, "
    "✏️ rename, 🔐 edit server access, 🗑 permanently remove (with confirmation). Bootstrap admins "
    "(configured via ADMIN_IDS) additionally see 🛡 Grant/Revoke admin, to promote or demote a "
    "user's DB-stored admin role without touching .env.\n\n"
    "<b>🖥 Manage Servers</b>:\n"
    "1. See all servers, or ➕ Add Server / ➕ Add GPU.\n"
    "2. Add Server: type a name. Add GPU: pick the server, type its index, model name, then pick "
    "a preset RAM size or ✏️ Other to type a custom MB value.\n"
    "3. Tap a server to rename/deactivate/activate/delete it (with confirmation), or tap one of "
    "its GPUs to rename/deactivate/activate/delete that GPU.\n\n"
    "<b>⚖️ Regulation</b>: tap a field (max RAM per reservation, max duration, booking horizon, "
    "time slot size, max active reservations per user, min. notice to self-cancel) and type its "
    "new value. Every field except the cancellation-notice one requires a positive whole number; "
    "that one also accepts 0, which disables the cancellation cutoff entirely. Admin "
    "cancellations (single, bulk, or override) always ignore this cutoff.\n\n"
    "<b>📊 Usage Report</b>: pick 👤 By User or 🖥 By GPU, then a date range preset, to get a bar "
    "chart of usage.\n\n"
    "<b>📋 All Reservations</b>:\n"
    "1. Pick 🗂 All Reservations (lab-wide) or 👤 By User (only students with upcoming "
    "reservations).\n"
    "2. Tap one reservation to cancel it, or use 🗑 Cancel All (this user) / 🗑 Cancel ALL "
    "Reservations for bulk cancellation — the lab-wide bulk cancel additionally requires typing "
    "CANCEL ALL to confirm.\n"
    "3. Any student whose reservation you cancel gets notified automatically."
)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"Your Telegram ID is: <code>{update.effective_user.id}</code>",
        parse_mode="HTML",
    )


async def prompt_admin_self_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Bootstrap admins (`ADMIN_IDS` in `.env`) always have menu access but, unlike students, are
    never issued an invite code -- so the first time one of them opens a student feature there's
    no `User` row yet to attach reservations/watches to. Sends a one-time name prompt and returns
    True if `update.effective_user` is such a bootstrap admin (the caller should transition to its
    "awaiting name" state); returns False for anyone else, who should see the normal
    not-registered message instead."""
    if not is_bootstrap_admin(update.effective_user.id, context):
        return False
    await update.effective_message.reply_text(
        "🛠 You're a lab admin without a student profile yet. What name should be shown on your "
        "reservations? Send your full name:"
    )
    return True


async def finish_admin_self_registration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    awaiting_state: int,
    resume: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[int]],
) -> int:
    """Handles the reply to `prompt_admin_self_registration`'s name prompt: creates the bootstrap
    admin's `User` row, then resumes whichever flow triggered registration (by re-running its
    `start`, now that a row exists for `get_active_user` to find)."""
    full_name = (update.effective_message.text or "").strip()
    if not full_name:
        await update.effective_message.reply_text("Please send your name as plain text.")
        return awaiting_state
    with session_scope() as session:
        user_service.register_user(session, update.effective_user.id, full_name)
    return await resume(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Main menu:") -> None:
    with session_scope() as session:
        admin = is_admin(session, update.effective_user.id, context)
    await update.effective_message.reply_text(text, reply_markup=main_menu_keyboard(admin))


async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "Admin panel:") -> None:
    columns = context.application.bot_data["config"].list_grids.admin_menu.columns
    await update.effective_message.reply_text(text, reply_markup=admin_menu_keyboard(columns))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    with session_scope() as session:
        user = get_active_user(session, telegram_id)
        if user is None and not is_admin(session, telegram_id, context):
            code = context.args[0] if context.args else None
            if code is None:
                await update.effective_message.reply_text(
                    "You're not registered for the DML Resource Manager yet.\n"
                    "Ask the lab admin for an invite code, then send /start <code> to register."
                )
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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT_STUDENT, parse_mode="HTML")
    with session_scope() as session:
        admin = is_admin(session, update.effective_user.id, context)
    if admin:
        await update.effective_message.reply_text(HELP_TEXT_ADMIN, parse_mode="HTML")


async def admin_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        allowed = is_admin(session, update.effective_user.id, context)
    if not allowed:
        await update.effective_message.reply_text("⛔ Admins only.")
        return
    await show_admin_menu(update, context)


async def back_to_main_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_main_menu(update, context)


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await show_main_menu(update, context, "Cancelled.")
    return ConversationHandler.END


async def cancel_wizard_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Like `cancel_wizard`, but for a Back press on an admin sub-flow's first screen -- steps
    back to the 🛠 Admin Panel menu (one level up) instead of all the way out to the Main Menu."""
    context.user_data.clear()
    await show_admin_menu(update, context)
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


async def render_paginated_step(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    items_key: str,
    prompt: str,
    state: int,
    *,
    columns: int = 1,
    rows: int = PAGE_SIZE,
) -> int:
    """Sends the keyboard for `context.user_data[items_key]` at the current page, for a plain
    (non-preset) paginated list step. Callers store the full item list under `items_key` once,
    then call this to (re-)render whichever page is current. `columns`/`rows` control the grid
    layout (see keyboards.paginated_list_keyboard); default is the original one-per-row list."""
    items = context.user_data[items_key]
    page = context.user_data.get("_page", 0)
    markup = paginated_list_keyboard(context, items, page, columns=columns, rows=rows)
    await update.effective_message.reply_text(prompt, reply_markup=markup)
    return state
