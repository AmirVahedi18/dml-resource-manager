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
from dml_bot.bot.keyboards import CANCEL_BUTTON, cancel_only_keyboard, server_list_keyboard
from dml_bot.bot.states import AdminServerStates
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import server_service


def _render_overview(session) -> str:
    servers = server_service.list_servers(session, active_only=False)
    if not servers:
        return "No servers configured yet."
    lines = []
    for s in servers:
        gpus = server_service.list_gpus(session, s, active_only=False)
        lines.append(f"<b>{s.name}</b>" + ("" if s.is_active else " (inactive)"))
        for g in gpus:
            lines.append(f"  GPU{g.index_on_server} · {g.model_name} · {g.total_ram_mb}MB")
    return "\n".join(lines)


def _menu_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("➕ Add Server", callback_data="adminservers:add_server")],
        [InlineKeyboardButton("➕ Add GPU", callback_data="adminservers:add_gpu")],
        [CANCEL_BUTTON],
    ]
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    if not await require_admin(update, context):
        return ConversationHandler.END

    with session_scope() as session:
        text = _render_overview(session)
    await update.callback_query.edit_message_text(text, reply_markup=_menu_keyboard(), parse_mode="HTML")
    return AdminServerStates.MENU


async def ask_server_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Send the new server's name:", reply_markup=cancel_only_keyboard()
    )
    return AdminServerStates.ADD_SERVER_NAME


async def receive_server_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Please send a non-empty server name.")
        return AdminServerStates.ADD_SERVER_NAME

    with session_scope() as session:
        try:
            server_service.create_server(session, name)
        except server_service.ServerAlreadyExistsError as exc:
            await update.message.reply_text(str(exc))
            return AdminServerStates.ADD_SERVER_NAME

    await update.message.reply_text(f"✅ Server '{name}' created.")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def ask_server_for_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    with session_scope() as session:
        servers = server_service.list_servers(session)

    if not servers:
        await update.callback_query.edit_message_text("Create a server first.")
        return ConversationHandler.END

    await update.callback_query.edit_message_text(
        "Add a GPU to which server?", reply_markup=server_list_keyboard(servers, "adminservers")
    )
    return AdminServerStates.CHOOSE_SERVER_FOR_GPU


async def choose_server_for_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    server_id = int(update.callback_query.data.split(":")[2])
    context.user_data["gpu_server_id"] = server_id

    await update.callback_query.edit_message_text(
        "Send the GPU's index on that server (e.g. 0):", reply_markup=cancel_only_keyboard()
    )
    return AdminServerStates.ADD_GPU_INDEX


async def receive_gpu_index(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        index_on_server = int(update.message.text.strip())
        if index_on_server < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a non-negative whole number.")
        return AdminServerStates.ADD_GPU_INDEX

    context.user_data["gpu_index"] = index_on_server
    await update.message.reply_text("Send the GPU model name (e.g. NVIDIA A100):")
    return AdminServerStates.ADD_GPU_MODEL


async def receive_gpu_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    model_name = update.message.text.strip()
    if not model_name:
        await update.message.reply_text("Please send a non-empty model name.")
        return AdminServerStates.ADD_GPU_MODEL

    context.user_data["gpu_model"] = model_name
    await update.message.reply_text("Send the GPU's total RAM in MB (e.g. 24576):")
    return AdminServerStates.ADD_GPU_RAM


async def receive_gpu_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        total_ram_mb = int(update.message.text.strip())
        if total_ram_mb <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a positive whole number of MB.")
        return AdminServerStates.ADD_GPU_RAM

    with session_scope() as session:
        server = session.get(Server, context.user_data["gpu_server_id"])
        try:
            gpu = server_service.add_gpu(
                session, server, context.user_data["gpu_index"], context.user_data["gpu_model"], total_ram_mb
            )
        except server_service.GPUIndexConflictError as exc:
            await update.message.reply_text(str(exc))
            return AdminServerStates.ADD_GPU_RAM
        message = f"✅ Added GPU{gpu.index_on_server} ({gpu.model_name}, {gpu.total_ram_mb}MB) to {server.name}."

    context.user_data.clear()
    await update.message.reply_text(message)
    await show_main_menu(update, context)
    return ConversationHandler.END


def servers_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start, pattern="^admin:servers$")],
        states={
            AdminServerStates.MENU: [
                CallbackQueryHandler(ask_server_name, pattern="^adminservers:add_server$"),
                CallbackQueryHandler(ask_server_for_gpu, pattern="^adminservers:add_gpu$"),
            ],
            AdminServerStates.ADD_SERVER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_server_name)
            ],
            AdminServerStates.CHOOSE_SERVER_FOR_GPU: [
                CallbackQueryHandler(choose_server_for_gpu, pattern=r"^adminservers:server:\d+$")
            ],
            AdminServerStates.ADD_GPU_INDEX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_gpu_index)
            ],
            AdminServerStates.ADD_GPU_MODEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_gpu_model)
            ],
            AdminServerStates.ADD_GPU_RAM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_gpu_ram)
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_wizard_callback, pattern="^wizard:cancel$")],
        name="admin_servers_conversation",
        persistent=False,
    )
