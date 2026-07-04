from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import require_admin
from dml_bot.bot.formatting import fmt_ram
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import (
    cancel_wizard,
    cancel_wizard_to_admin,
    handle_back_or_cancel,
    render_paginated_step,
    show_main_menu,
)
from dml_bot.bot_reply.keyboards import BACK, CONFIRM, MAIN_MENU, action_keyboard, cancel_only_keyboard, confirm_keyboard, paginated_list_keyboard
from dml_bot.bot_reply.presets import GPU_RAM_PRESETS_MB
from dml_bot.bot_reply.states import AdminServerStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import server_service

MENU_BUTTON = "🖥 Manage Servers"
ADD_SERVER = "➕ Add Server"
ADD_GPU = "➕ Add GPU"
GPU_RAM_OTHER = "✏️ Other (type MB)"


def _server_items(session) -> list[tuple[str, int]]:
    items = []
    for s in server_service.list_servers(session, active_only=False):
        flag = "✅" if s.is_active else "🚫"
        items.append((f"{s.name} {flag}", s.id))
    return items


async def _render_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("_viewing_server_id", None)
    context.user_data.pop("_viewing_gpu_id", None)
    with session_scope() as session:
        items = _server_items(session)
    context.user_data["_server_list_items"] = items
    page = context.user_data.get("_page", 0)
    grid = context.application.bot_data["config"].list_grids.server_list
    markup = paginated_list_keyboard(
        context, items, page, extra_rows=[[ADD_SERVER], [ADD_GPU]], columns=grid.columns, rows=grid.rows
    )
    text = "Servers (tap one to manage it):" if items else "No servers configured yet."
    await update.effective_message.reply_text(text, reply_markup=markup)
    return AdminServerStates.MENU


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_admin(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["_page"] = 0
    return await _render_menu(update, context)


def _server_detail_actions(server: Server, gpus: list[GPU]) -> list[tuple[str, tuple]]:
    actions = []
    for g in gpus:
        flag = "✅" if g.is_active else "🚫"
        actions.append(
            (f"{flag} GPU{g.index_on_server} · {g.model_name} ({fmt_ram(g.total_ram_mb)})", ("gpu", g.id))
        )
    actions.append(("✏️ Rename Server", ("rename_server", server.id)))
    actions.append(
        ("🚫 Deactivate Server" if server.is_active else "✅ Activate Server", ("toggle_server_active", server.id))
    )
    actions.append(("🗑 Remove Server", ("delete_server", server.id)))
    return actions


async def _show_server_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, server_id: int) -> int:
    context.user_data["_viewing_server_id"] = server_id
    with session_scope() as session:
        server = session.get(Server, server_id)
        gpus = server_service.list_gpus(session, server, active_only=False)
        text = f"<b>{server.name}</b>" + ("" if server.is_active else " (inactive)")
        actions = _server_detail_actions(server, gpus)
    markup = action_keyboard(context, actions)
    await update.effective_message.reply_text(text, reply_markup=markup, parse_mode="HTML")
    return AdminServerStates.SERVER_DETAIL


async def _show_gpu_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, gpu_id: int) -> int:
    context.user_data["_viewing_gpu_id"] = gpu_id
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        text = (
            f"<b>GPU{gpu.index_on_server} · {gpu.model_name}</b>\n"
            f"RAM: {fmt_ram(gpu.total_ram_mb)}\n"
            f"Status: {'active' if gpu.is_active else 'inactive'}"
        )
        actions = [
            ("✏️ Rename", ("rename_gpu", gpu.id)),
            ("🚫 Deactivate" if gpu.is_active else "✅ Activate", ("toggle_gpu_active", gpu.id)),
            ("🗑 Remove", ("delete_gpu", gpu.id)),
        ]
    markup = action_keyboard(context, actions)
    await update.effective_message.reply_text(text, reply_markup=markup, parse_mode="HTML")
    return AdminServerStates.GPU_DETAIL


async def _render_server_for_gpu_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await render_paginated_step(
        update, context, "_server_items", "Add a GPU to which server?", AdminServerStates.CHOOSE_SERVER_FOR_GPU
    )


async def menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == ADD_SERVER:
        await update.effective_message.reply_text("Send the new server's name:", reply_markup=cancel_only_keyboard())
        return AdminServerStates.ADD_SERVER_NAME
    if text == ADD_GPU:
        with session_scope() as session:
            items = [(s.name, s.id) for s in server_service.list_servers(session)]
        if not items:
            await update.effective_message.reply_text("Create a server first.")
            return await _render_menu(update, context)
        context.user_data["_server_items"] = items
        context.user_data["_page"] = 0
        return await _render_server_for_gpu_step(update, context)

    result = await handle_back_or_cancel(
        update, context, lambda: _render_menu(update, context), lambda: cancel_wizard_to_admin(update, context)
    )
    if result is not None:
        return result

    server_id = resolve_choice(context, text)
    if server_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return await _render_menu(update, context)

    return await _show_server_detail(update, context, server_id)


async def server_detail_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_menu(update, context)

    choice = resolve_choice(context, text)
    if choice is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminServerStates.SERVER_DETAIL

    kind, obj_id = choice
    if kind == "gpu":
        return await _show_gpu_detail(update, context, obj_id)
    if kind == "rename_server":
        await update.effective_message.reply_text("Send the new server name:", reply_markup=cancel_only_keyboard())
        return AdminServerStates.RENAME_SERVER
    if kind == "toggle_server_active":
        with session_scope() as session:
            server = session.get(Server, obj_id)
            server_service.set_server_active(session, server, not server.is_active)
        return await _show_server_detail(update, context, obj_id)

    with session_scope() as session:
        name = session.get(Server, obj_id).name
    await update.effective_message.reply_text(
        f"⚠️ Permanently delete server '{name}', its GPUs, and all their reservations/watches? "
        "This cannot be undone.",
        reply_markup=confirm_keyboard(),
    )
    return AdminServerStates.CONFIRM_DELETE_SERVER


async def receive_rename_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _show_server_detail(update, context, context.user_data["_viewing_server_id"])
    if not text:
        await update.effective_message.reply_text("Please send a non-empty server name.")
        return AdminServerStates.RENAME_SERVER

    with session_scope() as session:
        server = session.get(Server, context.user_data["_viewing_server_id"])
        try:
            server_service.rename_server(session, server, text)
        except server_service.ServerAlreadyExistsError as exc:
            await update.effective_message.reply_text(str(exc))
            return AdminServerStates.RENAME_SERVER

    await update.effective_message.reply_text(f"✅ Renamed to {text}.")
    return await _show_server_detail(update, context, context.user_data["_viewing_server_id"])


async def confirm_delete_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _show_server_detail(update, context, context.user_data["_viewing_server_id"])
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminServerStates.CONFIRM_DELETE_SERVER

    with session_scope() as session:
        server = session.get(Server, context.user_data["_viewing_server_id"])
        name = server.name
        server_service.delete_server(session, server)

    await update.effective_message.reply_text(f"🗑 Deleted server '{name}'.")
    return await _render_menu(update, context)


async def gpu_detail_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _show_server_detail(update, context, context.user_data["_viewing_server_id"])

    choice = resolve_choice(context, text)
    if choice is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminServerStates.GPU_DETAIL

    kind, gpu_id = choice
    if kind == "rename_gpu":
        await update.effective_message.reply_text(
            "Send the new GPU model name:", reply_markup=cancel_only_keyboard()
        )
        return AdminServerStates.RENAME_GPU
    if kind == "toggle_gpu_active":
        with session_scope() as session:
            gpu = session.get(GPU, gpu_id)
            server_service.set_gpu_active(session, gpu, not gpu.is_active)
        return await _show_gpu_detail(update, context, gpu_id)

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        label = f"GPU{gpu.index_on_server} ({gpu.model_name})"
    await update.effective_message.reply_text(
        f"⚠️ Permanently delete {label} and all its reservations/watches? This cannot be undone.",
        reply_markup=confirm_keyboard(),
    )
    return AdminServerStates.CONFIRM_DELETE_GPU


async def receive_rename_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _show_gpu_detail(update, context, context.user_data["_viewing_gpu_id"])
    if not text:
        await update.effective_message.reply_text("Please send a non-empty model name.")
        return AdminServerStates.RENAME_GPU

    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["_viewing_gpu_id"])
        server_service.rename_gpu(session, gpu, text)

    await update.effective_message.reply_text(f"✅ Renamed to {text}.")
    return await _show_gpu_detail(update, context, context.user_data["_viewing_gpu_id"])


async def confirm_delete_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _show_gpu_detail(update, context, context.user_data["_viewing_gpu_id"])
    if text != CONFIRM:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminServerStates.CONFIRM_DELETE_GPU

    with session_scope() as session:
        gpu = session.get(GPU, context.user_data["_viewing_gpu_id"])
        label = f"GPU{gpu.index_on_server} ({gpu.model_name})"
        server_service.delete_gpu(session, gpu)

    await update.effective_message.reply_text(f"🗑 Deleted {label}.")
    return await _show_server_detail(update, context, context.user_data["_viewing_server_id"])


async def receive_server_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.effective_message.text.strip()
    if name == MAIN_MENU:
        return await cancel_wizard(update, context)
    if name == BACK:
        return await _render_menu(update, context)
    if not name:
        await update.effective_message.reply_text("Please send a non-empty server name.")
        return AdminServerStates.ADD_SERVER_NAME

    with session_scope() as session:
        try:
            server_service.create_server(session, name)
        except server_service.ServerAlreadyExistsError as exc:
            await update.effective_message.reply_text(str(exc))
            return AdminServerStates.ADD_SERVER_NAME

    context.user_data.clear()
    await update.effective_message.reply_text(f"✅ Server '{name}' created.")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def choose_server_for_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    result = await handle_back_or_cancel(
        update, context, lambda: _render_server_for_gpu_step(update, context), lambda: _render_menu(update, context)
    )
    if result is not None:
        return result

    server_id = resolve_choice(context, update.effective_message.text)
    if server_id is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminServerStates.CHOOSE_SERVER_FOR_GPU
    context.user_data["gpu_server_id"] = server_id

    return await _render_gpu_index_prompt(update, context)


async def _render_gpu_index_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "Send the GPU's index on that server (e.g. 0):", reply_markup=cancel_only_keyboard()
    )
    return AdminServerStates.ADD_GPU_INDEX


async def receive_gpu_index(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_server_for_gpu_step(update, context)
    try:
        index_on_server = int(text)
        if index_on_server < 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Please send a non-negative whole number.")
        return AdminServerStates.ADD_GPU_INDEX

    context.user_data["gpu_index"] = index_on_server
    return await _render_gpu_model_prompt(update, context)


async def _render_gpu_model_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "Send the GPU model name (e.g. NVIDIA A100):", reply_markup=cancel_only_keyboard()
    )
    return AdminServerStates.ADD_GPU_MODEL


async def _render_gpu_ram_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    actions = [(fmt_ram(mb), mb) for mb in GPU_RAM_PRESETS_MB] + [(GPU_RAM_OTHER, "other")]
    markup = action_keyboard(context, actions)
    await update.effective_message.reply_text("Choose the GPU's total RAM:", reply_markup=markup)
    return AdminServerStates.ADD_GPU_RAM


async def receive_gpu_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    model_name = update.effective_message.text.strip()
    if model_name == MAIN_MENU:
        return await cancel_wizard(update, context)
    if model_name == BACK:
        return await _render_gpu_index_prompt(update, context)
    if not model_name:
        await update.effective_message.reply_text("Please send a non-empty model name.")
        return AdminServerStates.ADD_GPU_MODEL

    context.user_data["gpu_model"] = model_name
    return await _render_gpu_ram_step(update, context)


async def _create_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE, total_ram_mb: int) -> int:
    with session_scope() as session:
        server = session.get(Server, context.user_data["gpu_server_id"])
        try:
            gpu = server_service.add_gpu(
                session, server, context.user_data["gpu_index"], context.user_data["gpu_model"], total_ram_mb
            )
        except server_service.GPUIndexConflictError as exc:
            await update.effective_message.reply_text(str(exc))
            return await _render_gpu_ram_step(update, context)
        message = f"✅ Added GPU{gpu.index_on_server} ({gpu.model_name}, {fmt_ram(gpu.total_ram_mb)}) to {server.name}."

    context.user_data.clear()
    await update.effective_message.reply_text(message)
    await show_main_menu(update, context)
    return ConversationHandler.END


async def choose_gpu_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_gpu_model_prompt(update, context)

    choice = resolve_choice(context, text)
    if choice == "other":
        await update.effective_message.reply_text(
            "Send the GPU's total RAM in MB (e.g. 24576):", reply_markup=cancel_only_keyboard()
        )
        return AdminServerStates.ADD_GPU_RAM_CUSTOM
    if choice is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return AdminServerStates.ADD_GPU_RAM

    return await _create_gpu(update, context, choice)


async def receive_gpu_ram_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await _render_gpu_ram_step(update, context)
    try:
        total_ram_mb = int(text)
        if total_ram_mb <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Please send a positive whole number of MB.")
        return AdminServerStates.ADD_GPU_RAM_CUSTOM

    return await _create_gpu(update, context, total_ram_mb)


def servers_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            AdminServerStates.MENU: [MessageHandler(text_filter, menu_choice)],
            AdminServerStates.ADD_SERVER_NAME: [MessageHandler(text_filter, receive_server_name)],
            AdminServerStates.CHOOSE_SERVER_FOR_GPU: [MessageHandler(text_filter, choose_server_for_gpu)],
            AdminServerStates.ADD_GPU_INDEX: [MessageHandler(text_filter, receive_gpu_index)],
            AdminServerStates.ADD_GPU_MODEL: [MessageHandler(text_filter, receive_gpu_model)],
            AdminServerStates.ADD_GPU_RAM: [MessageHandler(text_filter, choose_gpu_ram)],
            AdminServerStates.ADD_GPU_RAM_CUSTOM: [MessageHandler(text_filter, receive_gpu_ram_custom)],
            AdminServerStates.SERVER_DETAIL: [MessageHandler(text_filter, server_detail_choice)],
            AdminServerStates.RENAME_SERVER: [MessageHandler(text_filter, receive_rename_server)],
            AdminServerStates.CONFIRM_DELETE_SERVER: [MessageHandler(text_filter, confirm_delete_server)],
            AdminServerStates.GPU_DETAIL: [MessageHandler(text_filter, gpu_detail_choice)],
            AdminServerStates.RENAME_GPU: [MessageHandler(text_filter, receive_rename_gpu)],
            AdminServerStates.CONFIRM_DELETE_GPU: [MessageHandler(text_filter, confirm_delete_gpu)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_admin_servers_conversation",
        persistent=False,
    )
