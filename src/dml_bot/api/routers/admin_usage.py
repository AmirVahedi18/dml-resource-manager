import io
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from dml_bot.api.deps import get_app_config, get_db_session, get_raw_init_data, require_admin
from dml_bot.api.templating import templates
from dml_bot.charts.usage_charts import render_bar_chart
from dml_bot.config.schema import AppConfig
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.user import User
from dml_bot.services import regulation_service, usage_service
from dml_bot.utils.time_utils import local_day_range_utc, utc_now

router = APIRouter(prefix="/api/admin/usage")

RANGE_LABELS = {
    "today": "today",
    "week": "past week",
    "month": "past 30 days",
    "horizon": "full booking horizon",
}


def _resolve_past_range(session: Session, range_key: str, tz_name: str):
    now = utc_now()
    if range_key == "today":
        return local_day_range_utc(now.date(), tz_name)
    if range_key == "week":
        return now - timedelta(days=7), now
    if range_key == "month":
        return now - timedelta(days=30), now
    regulation = regulation_service.get_regulation(session)
    return now - timedelta(days=regulation.booking_horizon_days), now


@router.get("")
async def choose_scope(request: Request, _admin=Depends(require_admin)):
    return templates.TemplateResponse(request, "partials/admin_usage_scope.html", {})


@router.get("/{scope}")
async def choose_range(scope: str, request: Request, _admin=Depends(require_admin)):
    return templates.TemplateResponse(
        request, "partials/admin_usage_range.html", {"scope": scope, "range_labels": RANGE_LABELS}
    )


@router.get("/{scope}/{range_key}")
async def show_chart(
    scope: str,
    range_key: str,
    request: Request,
    _admin=Depends(require_admin),
    raw_init_data: str = Depends(get_raw_init_data),
):
    return templates.TemplateResponse(
        request,
        "partials/admin_usage_chart.html",
        {"scope": scope, "range_key": range_key, "init_data": raw_init_data},
    )


@router.get("/{scope}/{range_key}/chart.png")
async def chart_png(
    scope: str,
    range_key: str,
    session: Session = Depends(get_db_session),
    _admin=Depends(require_admin),
    config: AppConfig = Depends(get_app_config),
):
    range_start, range_end = _resolve_past_range(session, range_key, config.bot.timezone)
    reservations = usage_service.get_reservations_in_range(session, range_start, range_end)

    if scope == "user":
        totals = usage_service.total_gpu_hours_by_user(reservations, range_start, range_end)
        labels = [session.get(User, uid).full_name for uid in totals]
        ylabel, title = "GPU-hours", "Usage by user"
    else:
        totals = usage_service.total_ram_hours_by_gpu(reservations, range_start, range_end)
        gpus = {gid: session.get(GPU, gid) for gid in totals}
        labels = [f"{gpus[gid].server.name} GPU{gpus[gid].index_on_server}" for gid in totals]
        ylabel, title = "MB-hours", "Usage by GPU"

    values = list(totals.values())
    if not values:
        labels, values = ["No data"], [0]

    png_bytes = render_bar_chart(labels, values, title, ylabel)
    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")
