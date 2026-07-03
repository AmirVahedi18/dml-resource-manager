from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import fmt_ram, watch_summary
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.gpu_picker import gpu_items, render_gpu_step
from dml_bot.bot_reply.handlers.common import (
    cancel_wizard,
    handle_back_or_cancel,
    render_paginated_step,
    resolve_preset_or_more,
    show_main_menu,
)
from dml_bot.bot_reply.keyboards import (
    BACK,
    CONFIRM,
    MAIN_MENU,
    action_keyboard,
    confirm_keyboard,
    paginated_list_keyboard,
    preset_keyboard,
)
from dml_bot.bot_reply.presets import RAM_THRESHOLD_PRESETS_MB, fine_ram_options
from dml_bot.bot_reply.states import WatchFlowStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.watch import WatchSubscription
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, watch_service
from dml_bot.utils.time_utils import local_day_range_utc, utc_now

MENU_BUTTON = "🔔 Watches"
NEW_WATCH = "➕ New Watch"
RANGE_PRESETS = [("Today", "today"), ("This week", "week"), ("Next 30 days", "month"), ("Full booking horizon", "horizon")]


def _watch_items(session, user_id: int, tz_name: str) -> list[tuple[str, int]]:
    watches = watch_service.list_watches_for_user(session, user_id)
    return [(f"❌ {watch_summary(w, w.gpu, w.gpu.server, tz_name).splitlines()[0]}", w.id) for w in watches]


async def _render_menu_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    items = context.user_data.get("_watch_items", [])
    page = context.user_data.get("_page", 0)
    markup = paginated_list_keyboard(context, items, page, extra_rows=[[NEW_WATCH]])
    text = "Your active watches (tap to cancel), or add a new one:" if items else "You have no active watches."
    await update.effective_message.reply_text(text, reply_markup=markup)
    return WatchFlowStates.MENU


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            await update.effective_message.reply_text("You're not registered yet.")
            return ConversationHandler.END
        items = _watch_items(session, user.id, tz_name)

    context.user_data.clear()
    context.user_data["_watch_items"] = items
    context.user_data["_page"] = 0
    return await _render_menu_step(update, context)


async def new_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        items = gpu_items(session)
    if not items:
        await update.effective_message.reply_text("No GPUs are configured yet.")
        return ConversationHandler.END
    context.user_data["_gpu_items"] = items
    context.user_data["_page"] = 0
    return await _render_gpu_step(update, context)


async def menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == NEW_WATCH:
        return await new_watch(update, context)

    result = await handle_back_or_cancel(
        update, context, lambda: _render_menu_step(update, context), lambda: cancel_wizard(update, context)
    )
    if result is not None:
        return result

    watch_id = resolve_choice(context, text)
    if watch_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.MENU
    context.user_data["watch_id"] = watch_id

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        watch = session.get(WatchSubscription, watch_id)
        text_out = "Cancel this watch?\n\n" + watch_summary(watch, watch.gpu, watch.gpu.server, tz_name)
    await update.effective_message.reply_text(text_out, reply_markup=confirm_keyboard())
    return WatchFlowStates.CONFIRM_CANCEL


async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_menu_step(update, context)
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.CONFIRM_CANCEL

    with session_scope() as session:
        watch = session.get(WatchSubscription, context.user_data["watch_id"])
        watch_service.cancel_watch(session, watch)

    context.user_data.clear()
    await update.effective_message.reply_text("✅ Watch cancelled.")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def _render_gpu_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_gpu_step(update, context, "Choose a GPU:", WatchFlowStates.CHOOSE_GPU)


async def _render_range_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    markup = action_keyboard(context, RANGE_PRESETS)
    await update.effective_message.reply_text("Watch which date range for free capacity?", reply_markup=markup)
    return WatchFlowStates.CHOOSE_RANGE


async def choose_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_gpu_step(update, context), lambda: _render_menu_step(update, context)
    )
    if result is not None:
        return result

    gpu_id = resolve_choice(context, update.effective_message.text)
    if gpu_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.CHOOSE_GPU
    context.user_data["gpu_id"] = gpu_id

    return await _render_range_step(update, context)


async def choose_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_gpu_step(update, context)

    range_key = resolve_choice(context, text)
    if range_key is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return WatchFlowStates.CHOOSE_RANGE

    tz_name = context.application.bot_data["config"].bot.timezone
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
        now = utc_now()
        if range_key == "today":
            range_start, range_end = local_day_range_utc(now.date(), tz_name)
        elif range_key == "week":
            range_start, range_end = now, now + timedelta(days=7)
        elif range_key == "month":
            range_start, range_end = now, now + timedelta(days=30)
        else:
            range_start, range_end = now, now + timedelta(days=regulation.booking_horizon_days)

    context.user_data["range_start"] = range_start.isoformat()
    context.user_data["range_end"] = range_end.isoformat()
    context.user_data["_ram_mode"] = "preset"
    return await _render_ram_presets(update, context)


async def _render_ram_presets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    markup = preset_keyboard(context, [(fmt_ram(mb), mb) for mb in RAM_THRESHOLD_PRESETS_MB])
    await update.effective_message.reply_text("Choose the minimum RAM you need to be notified about:", reply_markup=markup)
    return WatchFlowStates.CHOOSE_RAM


async def _render_ram_fine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["gpu_id"])
    context.user_data["_ram_fine_items"] = fine_ram_options(gpu.total_ram_mb)
    return await render_paginated_step(
        update, context, "_ram_fine_items", "Choose the minimum RAM:", WatchFlowStates.CHOOSE_RAM
    )


async def choose_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    state, ram_mb = await resolve_preset_or_more(
        update,
        context,
        "_ram_mode",
        lambda: _render_ram_presets(update, context),
        lambda: _render_ram_fine(update, context),
        lambda: _render_range_step(update, context),
    )
    if state is not None:
        return state

    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        gpu = session.get(GPU, context.user_data["gpu_id"])
        range_start = datetime.fromisoformat(context.user_data["range_start"])
        range_end = datetime.fromisoformat(context.user_data["range_end"])
        watch_service.create_watch(session, user, gpu, range_start, range_end, ram_mb)

    context.user_data.clear()
    await update.effective_message.reply_text("✅ Watch created — you'll be notified when enough RAM frees up.")
    await show_main_menu(update, context)
    return ConversationHandler.END


def watch_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            WatchFlowStates.MENU: [MessageHandler(text_filter, menu_choice)],
            WatchFlowStates.CONFIRM_CANCEL: [MessageHandler(text_filter, confirm_cancel)],
            WatchFlowStates.CHOOSE_GPU: [MessageHandler(text_filter, choose_gpu)],
            WatchFlowStates.CHOOSE_RANGE: [MessageHandler(text_filter, choose_range)],
            WatchFlowStates.CHOOSE_RAM: [MessageHandler(text_filter, choose_ram)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_watch_conversation",
        persistent=False,
    )
