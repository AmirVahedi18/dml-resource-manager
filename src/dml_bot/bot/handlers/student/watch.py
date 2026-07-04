from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from dml_bot.bot.auth import get_active_user
from dml_bot.bot.formatting import watch_summary
from dml_bot.bot.handlers.common import cancel_wizard_callback, show_main_menu
from dml_bot.bot.keyboards import (
    CANCEL_BUTTON,
    cancel_only_keyboard,
    confirm_keyboard,
    gpu_list_keyboard,
    range_picker_keyboard,
    server_list_keyboard,
    yes_no_keyboard,
)
from dml_bot.bot.states import WatchFlowStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.models.watch import WatchSubscription
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, server_service, watch_service
from dml_bot.utils.time_utils import local_day_range_utc, utc_now


def _menu_keyboard(watches, tz_name: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"❌ {watch_summary(w, w.gpu, w.gpu.server, tz_name).splitlines()[0]}", callback_data=f"watchlist:choose:{w.id}")]
        for w in watches
    ]
    rows.append([InlineKeyboardButton("➕ New Watch", callback_data="watch:new")])
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    tz_name = context.application.bot_data["config"].bot.timezone

    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        if user is None:
            await update.callback_query.edit_message_text("You're not registered yet.")
            return ConversationHandler.END
        watches = watch_service.list_watches_for_user(session, user.id)
        text = "Your active watches (tap to cancel), or add a new one:" if watches else "You have no active watches."
        markup = _menu_keyboard(watches, tz_name)

    context.user_data.clear()
    await update.callback_query.edit_message_text(text, reply_markup=markup)
    return WatchFlowStates.MENU


async def choose_existing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    watch_id = int(update.callback_query.data.split(":")[2])
    context.user_data["watch_id"] = watch_id
    tz_name = context.application.bot_data["config"].bot.timezone

    with session_scope() as session:
        watch = session.get(WatchSubscription, watch_id)
        text = "Cancel this watch?\n\n" + watch_summary(watch, watch.gpu, watch.gpu.server, tz_name)

    await update.callback_query.edit_message_text(text, reply_markup=confirm_keyboard("watchlist"))
    return WatchFlowStates.CONFIRM_CANCEL


async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    with session_scope() as session:
        watch = session.get(WatchSubscription, context.user_data["watch_id"])
        watch_service.cancel_watch(session, watch)

    context.user_data.clear()
    await update.callback_query.edit_message_text("✅ Watch cancelled.")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def new_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    with session_scope() as session:
        servers = server_service.list_servers(session)

    await update.callback_query.edit_message_text(
        "Choose a server:", reply_markup=server_list_keyboard(servers, "watch")
    )
    return WatchFlowStates.CHOOSE_SERVER


async def choose_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    server_id = int(update.callback_query.data.split(":")[2])
    context.user_data["server_id"] = server_id

    with session_scope() as session:
        server = session.get(Server, server_id)
        gpus = server_service.list_gpus(session, server)

    if not gpus:
        await update.callback_query.edit_message_text("This server has no active GPUs.")
        return ConversationHandler.END

    await update.callback_query.edit_message_text(
        "Choose a GPU:", reply_markup=gpu_list_keyboard(gpus, "watch")
    )
    return WatchFlowStates.CHOOSE_GPU


async def choose_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    gpu_id = int(update.callback_query.data.split(":")[2])
    context.user_data["gpu_id"] = gpu_id

    await update.callback_query.edit_message_text(
        "Watch which date range for free capacity?", reply_markup=range_picker_keyboard("watch")
    )
    return WatchFlowStates.CHOOSE_RANGE


async def choose_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    range_key = update.callback_query.data.split(":")[2]
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

    await update.callback_query.edit_message_text(
        "Type the minimum RAM (MB) you need to be notified about:", reply_markup=cancel_only_keyboard()
    )
    return WatchFlowStates.CHOOSE_RAM


async def choose_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        ram_mb = int(update.message.text.strip())
        if ram_mb <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a positive whole number of MB, e.g. 4096")
        return WatchFlowStates.CHOOSE_RAM

    context.user_data["ram_mb"] = ram_mb
    await update.message.reply_text(
        "Auto-book the slot the instant it frees (from whenever it frees, capped by the lab's "
        "max reservation duration), or just get notified so you can pick manually?",
        reply_markup=yes_no_keyboard("watch:autobook:yes", "watch:autobook:no"),
    )
    return WatchFlowStates.CHOOSE_AUTO_BOOK


async def choose_auto_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    auto_book = update.callback_query.data.split(":")[2] == "yes"

    from datetime import datetime as dt_cls

    range_start = dt_cls.fromisoformat(context.user_data["range_start"])
    range_end = dt_cls.fromisoformat(context.user_data["range_end"])

    with session_scope() as session:
        user = get_active_user(session, update.effective_user.id)
        gpu = session.get(GPU, context.user_data["gpu_id"])
        watch_service.create_watch(
            session, user, gpu, range_start, range_end, context.user_data["ram_mb"], auto_book=auto_book
        )

    context.user_data.clear()
    text = (
        "✅ Watch created — the slot will be booked for you automatically the instant it frees."
        if auto_book
        else "✅ Watch created — you'll be notified when enough RAM frees up."
    )
    await update.callback_query.edit_message_text(text)
    await show_main_menu(update, context)
    return ConversationHandler.END


def watch_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^menu:watches$")],
        states={
            WatchFlowStates.MENU: [
                CallbackQueryHandler(new_watch, pattern="^watch:new$"),
                CallbackQueryHandler(choose_existing, pattern=r"^watchlist:choose:\d+$"),
            ],
            WatchFlowStates.CONFIRM_CANCEL: [
                CallbackQueryHandler(confirm_cancel, pattern="^watchlist:confirm$")
            ],
            WatchFlowStates.CHOOSE_SERVER: [CallbackQueryHandler(choose_server, pattern=r"^watch:server:\d+$")],
            WatchFlowStates.CHOOSE_GPU: [CallbackQueryHandler(choose_gpu, pattern=r"^watch:gpu:\d+$")],
            WatchFlowStates.CHOOSE_RANGE: [CallbackQueryHandler(choose_range, pattern=r"^watch:range:\w+$")],
            WatchFlowStates.CHOOSE_RAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_ram)],
            WatchFlowStates.CHOOSE_AUTO_BOOK: [
                CallbackQueryHandler(choose_auto_book, pattern=r"^watch:autobook:(yes|no)$")
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="watch_conversation",
        persistent=False,
    )
