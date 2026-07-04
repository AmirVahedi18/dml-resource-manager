"""Shared "choose a GPU" step used by reserve/schedule/watch -- all three flatten the legacy
"choose a server, then choose a GPU" pair of screens into one paginated list of every GPU the
caller has access to.
"""
from telegram import Update
from telegram.ext import ContextTypes

from dml_bot.bot.auth import is_admin
from dml_bot.bot.formatting import fmt_ram
from dml_bot.bot_reply.handlers.common import render_paginated_step
from dml_bot.services import server_access_service, server_service


def gpu_items(session, accessible_server_ids: set[int] | None = None) -> list[tuple[str, int]]:
    """`accessible_server_ids=None` means unrestricted (admins); otherwise only GPUs on servers in
    that set are listed."""
    items = []
    for server in server_service.list_servers(session):
        if accessible_server_ids is not None and server.id not in accessible_server_ids:
            continue
        for gpu in server_service.list_gpus(session, server):
            label = f"{server.name} · GPU{gpu.index_on_server} ({gpu.model_name}, {fmt_ram(gpu.total_ram_mb)})"
            items.append((label, gpu.id))
    return items


def accessible_server_ids_for(
    session, telegram_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE
) -> set[int] | None:
    """Admins implicitly have access to every server (returns None, meaning "unrestricted" to
    gpu_items); students are restricted to whichever servers the admin has explicitly granted."""
    if is_admin(session, telegram_id, context):
        return None
    return server_access_service.list_accessible_server_ids(session, user_id)


async def render_gpu_step(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, state: int) -> int:
    return await render_paginated_step(update, context, "_gpu_items", prompt, state)
