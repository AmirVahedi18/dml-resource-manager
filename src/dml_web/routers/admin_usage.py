from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from dml_bot.config.schema import AppConfig
from dml_bot.db.models.user import User
from dml_bot.services import reservation_service, server_service, usage_service
from dml_bot.utils.time_utils import local_day_range_utc, to_naive_utc
from dml_web import chart_data
from dml_web.deps import get_app_cfg, get_session, require_admin
from dml_web.schemas.admin_usage import RankedUsageOut

router = APIRouter()


@router.get("/ranked", response_model=RankedUsageOut)
def ranked_usage(
    range_start: datetime = Query(...),
    range_end: datetime = Query(...),
    metric: Literal["gpu_hours", "ram_gb_hours"] = Query("gpu_hours"),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> RankedUsageOut:
    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    reservations = usage_service.get_reservations_in_range(session, range_start, range_end)

    if metric == "gpu_hours":
        totals = usage_service.total_gpu_hours_by_user(reservations, range_start, range_end)
        labels, values = [], []
        for user_id, hours in totals.items():
            user = session.get(User, user_id)
            labels.append(user.full_name if user else f"user {user_id}")
            values.append(hours)
        return RankedUsageOut(metric=metric, unit="GPU-hours", labels=labels, values=values)

    totals = usage_service.total_ram_hours_by_gpu(reservations, range_start, range_end)
    labels, values = [], []
    for gpu_id, mb_hours in totals.items():
        gpu = server_service.get_gpu(session, gpu_id)
        labels.append(f"{gpu.server.name} GPU{gpu.index_on_server}" if gpu else f"gpu {gpu_id}")
        values.append(mb_hours / 1024)  # MB-hours -> GB-hours
    return RankedUsageOut(metric=metric, unit="GB-hours", labels=labels, values=values)


@router.get("/historical-availability")
def historical_availability(
    gpu_id: int = Query(...),
    start_date: date = Query(...),
    days: int = Query(..., gt=0),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
    app_cfg: AppConfig = Depends(get_app_cfg),
) -> dict:
    gpu = server_service.get_gpu(session, gpu_id)
    if gpu is None:
        raise HTTPException(404, "GPU not found")

    tz_name = app_cfg.bot.timezone
    range_start, _ = local_day_range_utc(start_date, tz_name)
    range_end = range_start + timedelta(days=days)

    reservations = reservation_service.list_reservations_for_gpu(session, gpu.id, range_start, range_end)
    return chart_data.build_occupancy_chart(
        reservations, gpu.total_ram_mb, range_start, range_end, tz_name, chart_data.historical_bucket_hours(days)
    )
