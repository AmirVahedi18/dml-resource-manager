"""Picks the admin-configured chart renderer (see `chart_settings_service`) and sends the result
-- the legacy text chart as one or more `<pre>`-wrapped messages, any Plotly variant as a single
PNG photo -- so the three screens that show this chart (Reserve GPU, View Schedule, Watches) don't
each duplicate the render-then-send branching.
"""
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from dml_bot.bot_reply.ram_chart import render_ram_chart
from dml_bot.bot_reply.ram_chart_plotly import render_bucketed_bars, render_gantt, render_stacked_area
from dml_bot.db.session import session_scope
from dml_bot.services import chart_settings_service

_PLOTLY_RENDERERS = {
    "plotly_bars": lambda reservations, cap_mb, range_start, range_end, tz_name, bucket_hours, title: render_bucketed_bars(
        reservations, cap_mb, range_start, range_end, tz_name, bucket_hours, title
    ),
    "plotly_area": lambda reservations, cap_mb, range_start, range_end, tz_name, bucket_hours, title: render_stacked_area(
        reservations, cap_mb, range_start, range_end, tz_name, title
    ),
    "plotly_gantt": lambda reservations, cap_mb, range_start, range_end, tz_name, bucket_hours, title: render_gantt(
        reservations, range_start, range_end, tz_name, title
    ),
}


async def send_ram_chart(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reservations: list,
    cap_mb: int,
    range_start: datetime,
    range_end: datetime,
    tz_name: str,
    header_html: str,
    title_plain: str,
    bucket_hours: float | None = None,
) -> None:
    """`header_html` (e.g. "<b>lab-server-1 GPU0</b> -- next 7 days") is used for the legacy
    chart's separate header message; `title_plain` (no markup) is baked into the Plotly image
    itself, since Plotly renders its own title text rather than parsing Telegram HTML.
    `bucket_hours` overrides `schedule_chart.bucket_hours` -- callers with an admin-chosen (rather
    than fixed-config) range pass a duration-scaled value so a long historical window doesn't
    blow up into thousands of buckets.

    All screens that show this chart (Reserve GPU's and Watches' pre-date-picker availability
    charts, View Schedule, and Usage Report's Historical Availability) render with the same
    admin-configured renderer (see `chart_settings_service`) -- there's exactly one renderer
    choice, not one per screen."""
    with session_scope() as session:
        renderer = chart_settings_service.get_renderer(session)

    config = context.application.bot_data["config"].schedule_chart
    effective_bucket_hours = bucket_hours if bucket_hours is not None else config.bucket_hours

    if renderer not in _PLOTLY_RENDERERS:
        await update.effective_message.reply_text(header_html, parse_mode="HTML")
        pages = render_ram_chart(
            reservations, cap_mb, range_start, range_end, tz_name, effective_bucket_hours, config.max_width_chars
        )
        for page in pages:
            await update.effective_message.reply_text(f"<pre>{page}</pre>", parse_mode="HTML")
        return

    png = _PLOTLY_RENDERERS[renderer](
        reservations, cap_mb, range_start, range_end, tz_name, effective_bucket_hours, title_plain
    )
    await update.effective_message.reply_photo(photo=png)
