from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from dml_core.config.schema import AppConfig
from dml_core.db.models.server import Server
from dml_core.db.models.user import User
from dml_core.services import regulation_service, reservation_service, server_service
from dml_core.utils.time_utils import to_naive_utc, utc_now
from dml_web import access, chart_data
from dml_web.deps import get_app_cfg, get_current_user, get_session
from dml_web.schemas.schedule import (
    FreeRamOut,
    GpuOut,
    GpuOverviewOut,
    RegulationOut,
    ServerOut,
    ServerOverviewOut,
)

router = APIRouter()


@router.get("/regulation", response_model=RegulationOut)
def get_regulation(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
    app_cfg: AppConfig = Depends(get_app_cfg),
) -> RegulationOut:
    regulation = regulation_service.get_regulation(session)
    out = RegulationOut.model_validate(regulation)
    out.timezone = app_cfg.timezone
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


@router.get("/overview", response_model=list[ServerOverviewOut])
def get_overview(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> list[ServerOverviewOut]:
    """Live free/used RAM per GPU across every server the user can access, in one request.

    "Used now" = sum of RAM held by reservations active at this instant; since they all
    overlap "now", their sum is exactly the current peak concurrent usage on the GPU.
    """
    now = utc_now()
    servers = server_service.list_servers(session)
    accessible = access.accessible_server_ids(session, user)
    if accessible is not None:
        servers = [s for s in servers if s.id in accessible]

    overview: list[ServerOverviewOut] = []
    for server in servers:
        gpu_outs: list[GpuOverviewOut] = []
        for gpu in server_service.list_gpus(session, server):
            active = reservation_service.get_overlapping_active_reservations(session, gpu.id, now, now)
            used = sum(r.ram_mb for r in active)
            gpu_outs.append(
                GpuOverviewOut(
                    id=gpu.id,
                    index_on_server=gpu.index_on_server,
                    model_name=gpu.model_name,
                    total_ram_mb=gpu.total_ram_mb,
                    used_ram_mb=used,
                    free_ram_mb=max(gpu.total_ram_mb - used, 0),
                    active_reservations=len(active),
                )
            )
        overview.append(ServerOverviewOut(id=server.id, name=server.name, gpus=gpu_outs))
    return overview


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
        reservations, gpu.total_ram_mb, range_start, range_end, app_cfg.timezone, effective_bucket_hours
    )


@router.get("/gpus/{gpu_id}/free-ram", response_model=FreeRamOut)
def get_free_ram(
    gpu_id: int,
    start: datetime = Query(...),
    end: datetime = Query(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> FreeRamOut:
    """The minimum free RAM held throughout [start, end) -- i.e. the most this exact window
    could actually be booked for, used to preview a reservation's feasibility before submit."""
    gpu = server_service.get_gpu(session, gpu_id)
    if gpu is None:
        raise HTTPException(404, "GPU not found")
    access.ensure_gpu_access(session, user, gpu)

    free_ram_mb = reservation_service.min_free_ram_in_range(session, gpu, start, end)
    return FreeRamOut(free_ram_mb=free_ram_mb)
