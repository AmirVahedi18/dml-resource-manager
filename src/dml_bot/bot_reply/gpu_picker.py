"""Shared "choose a GPU" step used by reserve/schedule/watch -- all three flatten the legacy
"choose a server, then choose a GPU" pair of screens into one paginated list of every GPU lab-wide.
"""
from telegram import Update
from telegram.ext import ContextTypes

from dml_bot.bot.formatting import fmt_ram
from dml_bot.bot_reply.handlers.common import render_paginated_step
from dml_bot.services import server_service


def gpu_items(session) -> list[tuple[str, int]]:
    items = []
    for server in server_service.list_servers(session):
        for gpu in server_service.list_gpus(session, server):
            label = f"{server.name} · GPU{gpu.index_on_server} ({gpu.model_name}, {fmt_ram(gpu.total_ram_mb)})"
            items.append((label, gpu.id))
    return items


async def render_gpu_step(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, state: int) -> int:
    return await render_paginated_step(update, context, "_gpu_items", prompt, state)
