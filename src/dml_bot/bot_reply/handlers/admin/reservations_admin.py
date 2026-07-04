from datetime import timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import require_admin
from dml_bot.bot.formatting import fmt_dt, fmt_ram, reservation_summary
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import (
    cancel_wizard,
    cancel_wizard_to_admin,
    handle_back_or_cancel,
    render_paginated_step,
    show_main_menu,
)
from dml_bot.bot_reply.keyboards import (
    BACK,
    CONFIRM,
    MAIN_MENU,
    action_keyboard,
    cancel_only_keyboard,
    confirm_keyboard,
    paginated_list_keyboard,
)
from dml_bot.bot_reply.states import AdminReservationsStates
from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, usage_service
from dml_bot.utils.time_utils import utc_now

MENU_BUTTON = "📋 All Reservations"
SCOPE_ALL = "🗂 All Reservations"
SCOPE_BY_USER = "👤 By User"
CANCEL_ALL_LAB = "🗑 Cancel ALL Reservations"
CANCEL_ALL_USER = "🗑 Cancel All (this user)"
LAB_WIDE_CONFIRM_PHRASE = "CANCEL ALL"


def _reservation_items(session, tz_name: str, user_id: int | None = None) -> list[tuple[str, int]]:
    regulation = regulation_service.get_regulation(session)
    now = utc_now()
    reservations = usage_service.get_reservations_in_range(
        session, now, now + timedelta(days=regulation.booking_horizon_days), user_id=user_id
    )
    reservations.sort(key=lambda r: r.start_time)
    return [
        (
            f"{r.gpu.server.name} GPU{r.gpu.index_on_server} · {r.user.full_name} · "
            f"{fmt_dt(r.start_time, tz_name)} → {fmt_dt(r.end_time, tz_name)} · {fmt_ram(r.ram_mb)}",
            r.id,
        )
        for r in reservations
    ]


def _user_items(session) -> list[tuple[str, int]]:
    return [(u.full_name, u.id) for u in reservation_service.list_users_with_active_reservations(session)]


async def _notify_cancelled(bot, reservation, tz_name: str) -> None:
    text = "🚫 Your reservation was cancelled by an admin.\n\n" + reservation_summary(
        reservation, reservation.gpu, reservation.gpu.server, tz_name
    )
    await bot.send_message(chat_id=reservation.user.telegram_id, text=text, parse_mode="HTML")


async def _render_scope_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    markup = action_keyboard(context, [(SCOPE_ALL, "all"), (SCOPE_BY_USER, "user")])
    await update.effective_message.reply_text("View reservations:", reply_markup=markup)
    return AdminReservationsStates.CHOOSE_SCOPE


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_admin(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    return await _render_scope_step(update, context)


async def _render_user_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    grid = context.application.bot_data["config"].list_grids.user_list
    return await render_paginated_step(
        update,
        context,
        "_user_items",
        "Choose a student to view their reservations:",
        AdminReservationsStates.CHOOSE_USER,
        columns=grid.columns,
        rows=grid.rows,
    )


async def _render_list_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    scope = context.user_data.get("_scope", "all")
    items = context.user_data.get("_reservation_items", [])
    page = context.user_data.get("_page", 0)

    if scope == "all":
        prompt = "All upcoming reservations (tap one to cancel it):" if items else "No upcoming reservations lab-wide."
        extra_rows = [[CANCEL_ALL_LAB]] if items else None
    else:
        with session_scope() as session:
            user_name = session.get(User, context.user_data["_admin_user_id"]).full_name
        prompt = (
            f"{user_name}'s upcoming reservations (tap one to cancel it):"
            if items
            else f"{user_name} has no upcoming reservations."
        )
        extra_rows = [[CANCEL_ALL_USER]] if items else None

    markup = paginated_list_keyboard(context, items, page, extra_rows=extra_rows)
    await update.effective_message.reply_text(prompt, reply_markup=markup)
    return AdminReservationsStates.CHOOSE_RESERVATION


async def choose_scope(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:  # this is the first screen, so Back steps up to the Admin Panel menu
        return await cancel_wizard_to_admin(update, context)

    scope = resolve_choice(context, text)
    if scope is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminReservationsStates.CHOOSE_SCOPE

    tz_name = context.application.bot_data["config"].bot.timezone
    if scope == "all":
        with session_scope() as session:
            items = _reservation_items(session, tz_name)
        context.user_data["_scope"] = "all"
        context.user_data["_reservation_items"] = items
        context.user_data["_page"] = 0
        return await _render_list_step(update, context)

    with session_scope() as session:
        user_items = _user_items(session)
    if not user_items:
        await update.effective_message.reply_text("No students currently have upcoming reservations.")
        return await _render_scope_step(update, context)

    context.user_data["_user_items"] = user_items
    context.user_data["_page"] = 0
    return await _render_user_step(update, context)


async def choose_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_user_step(update, context), lambda: _render_scope_step(update, context)
    )
    if result is not None:
        return result

    user_id = resolve_choice(context, update.effective_message.text)
    if user_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminReservationsStates.CHOOSE_USER

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        items = _reservation_items(session, tz_name, user_id=user_id)

    context.user_data["_scope"] = "user"
    context.user_data["_admin_user_id"] = user_id
    context.user_data["_reservation_items"] = items
    context.user_data["_page"] = 0
    return await _render_list_step(update, context)


async def _render_type_confirm_cancel_all_lab(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    count = len(context.user_data.get("_reservation_items", []))
    await update.effective_message.reply_text(
        f"⚠️ This will permanently cancel ALL {count} upcoming reservation(s) lab-wide. This cannot "
        f"be undone.\n\nType {LAB_WIDE_CONFIRM_PHRASE} to confirm, or ◀ Back to cancel.",
        reply_markup=cancel_only_keyboard(),
    )
    return AdminReservationsStates.TYPE_CONFIRM_CANCEL_ALL_LAB


async def _render_confirm_cancel_all_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        user_name = session.get(User, context.user_data["_admin_user_id"]).full_name
    count = len(context.user_data.get("_reservation_items", []))
    await update.effective_message.reply_text(
        f"⚠️ Cancel all {count} upcoming reservation(s) for {user_name}? This cannot be undone.",
        reply_markup=confirm_keyboard(),
    )
    return AdminReservationsStates.CONFIRM_CANCEL_ALL_USER


async def choose_reservation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    scope = context.user_data.get("_scope", "all")
    back_render = (
        (lambda: _render_scope_step(update, context))
        if scope == "all"
        else (lambda: _render_user_step(update, context))
    )
    result = await handle_back_or_cancel(update, context, lambda: _render_list_step(update, context), back_render)
    if result is not None:
        return result

    if scope == "all" and text == CANCEL_ALL_LAB:
        return await _render_type_confirm_cancel_all_lab(update, context)
    if scope == "user" and text == CANCEL_ALL_USER:
        return await _render_confirm_cancel_all_user(update, context)

    reservation_id = resolve_choice(context, text)
    if reservation_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminReservationsStates.CHOOSE_RESERVATION
    context.user_data["reservation_id"] = reservation_id

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, reservation_id)
        detail_text = (
            f"Cancel this reservation (admin override)?\n\n"
            f"{reservation.gpu.server.name} GPU{reservation.gpu.index_on_server}\n"
            f"Student: {reservation.user.full_name}\n"
            f"{fmt_dt(reservation.start_time, tz_name)} → {fmt_dt(reservation.end_time, tz_name)}\n"
            f"RAM: {fmt_ram(reservation.ram_mb)}"
        )
    await update.effective_message.reply_text(detail_text, reply_markup=confirm_keyboard())
    return AdminReservationsStates.CONFIRM_CANCEL


async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_list_step(update, context)
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminReservationsStates.CONFIRM_CANCEL

    tz_name = context.application.bot_data["config"].bot.timezone
    bot = update.get_bot()
    with session_scope() as session:
        reservation = session.get(reservation_service.Reservation, context.user_data["reservation_id"])
        reservation_service.cancel_reservation(session, reservation)
        await _notify_cancelled(bot, reservation, tz_name)

    context.user_data.clear()
    await update.effective_message.reply_text("✅ Reservation cancelled by admin.")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def confirm_cancel_all_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_list_step(update, context)
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminReservationsStates.CONFIRM_CANCEL_ALL_USER

    tz_name = context.application.bot_data["config"].bot.timezone
    bot = update.get_bot()
    user_id = context.user_data["_admin_user_id"]
    with session_scope() as session:
        user = session.get(User, user_id)
        name = user.full_name
        reservations = reservation_service.list_active_reservations_for_user(session, user_id)
        count = reservation_service.cancel_reservations(session, reservations)
        for reservation in reservations:
            await _notify_cancelled(bot, reservation, tz_name)

    context.user_data.clear()
    await update.effective_message.reply_text(f"🗑 Cancelled {count} reservation(s) for {name}.")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def confirm_cancel_all_lab(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_list_step(update, context)
    if text.upper() != LAB_WIDE_CONFIRM_PHRASE:
        await update.effective_message.reply_text(
            f"Type exactly '{LAB_WIDE_CONFIRM_PHRASE}' to confirm, or ◀ Back to cancel."
        )
        return AdminReservationsStates.TYPE_CONFIRM_CANCEL_ALL_LAB

    tz_name = context.application.bot_data["config"].bot.timezone
    bot = update.get_bot()
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
        now = utc_now()
        reservations = usage_service.get_reservations_in_range(
            session, now, now + timedelta(days=regulation.booking_horizon_days)
        )
        count = reservation_service.cancel_reservations(session, reservations, now=now)
        for reservation in reservations:
            await _notify_cancelled(bot, reservation, tz_name)

    context.user_data.clear()
    await update.effective_message.reply_text(f"🗑 Cancelled {count} reservation(s) lab-wide.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def admin_reservations_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            AdminReservationsStates.CHOOSE_SCOPE: [MessageHandler(text_filter, choose_scope)],
            AdminReservationsStates.CHOOSE_USER: [MessageHandler(text_filter, choose_user)],
            AdminReservationsStates.CHOOSE_RESERVATION: [MessageHandler(text_filter, choose_reservation)],
            AdminReservationsStates.CONFIRM_CANCEL: [MessageHandler(text_filter, confirm_cancel)],
            AdminReservationsStates.CONFIRM_CANCEL_ALL_USER: [MessageHandler(text_filter, confirm_cancel_all_user)],
            AdminReservationsStates.TYPE_CONFIRM_CANCEL_ALL_LAB: [
                MessageHandler(text_filter, confirm_cancel_all_lab)
            ],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_admin_reservations_conversation",
        persistent=False,
    )
