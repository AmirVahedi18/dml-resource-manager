from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from dml_bot.config.schema import AppConfig
from dml_bot.db.models.server import Server
from dml_bot.db.models.user import User
from dml_bot.services import regulation_service, reservation_service, server_service
from dml_bot.utils.time_utils import to_naive_utc
from dml_web import access, chart_data
from dml_web.deps import get_app_cfg, get_current_user, get_session
from dml_web.schemas.schedule import GpuOut, RegulationOut, ServerOut

router = APIRouter()


@router.get("/regulation", response_model=RegulationOut)
def get_regulation(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    app_cfg: AppConfig = Depends(get_app_cfg),
) -> RegulationOut:
    regulation = regulation_service.get_regulation(session)
    out = RegulationOut.model_validate(regulation)
    out.timezone = app_cfg.bot.timezone
    return out


@router.get("/servers", response_model=list[ServerOut])
def list_servers(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> list[Server]:
    servers = server_service.list_servers(session)
    accessible = access.accessible_server_ids(session, user)
    if accessible is not None:
        servers = [s for s in servers if s.id in accessible]
    return servers


@router.get("/servers/{server_id}/gpus", response_model=list[GpuOut])
def list_gpus(
    server_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    access.ensure_server_access(session, user, server_id)
    server = session.get(Server, server_id)
    if server is None:
        raise HTTPException(404, "Server not found")
    return server_service.list_gpus(session, server)


@router.get("/gpus/{gpu_id}/availability")
def get_availability(
    gpu_id: int,
    range_start: datetime = Query(...),
    range_end: datetime = Query(...),
    bucket_hours: float | None = Query(None, gt=0),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    app_cfg: AppConfig = Depends(get_app_cfg),
) -> dict:
    gpu = server_service.get_gpu(session, gpu_id)
    if gpu is None:
        raise HTTPException(404, "GPU not found")
    access.ensure_gpu_access(session, user, gpu)

    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    reservations = reservation_service.list_reservations_for_gpu(session, gpu.id, range_start, range_end)
    effective_bucket_hours = bucket_hours if bucket_hours is not None else app_cfg.schedule_chart.bucket_hours
    return chart_data.build_occupancy_chart(
        reservations, gpu.total_ram_mb, range_start, range_end, app_cfg.bot.timezone, effective_bucket_hours
    )
