from datetime import timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from dml_bot.api.deps import get_app_config, get_current_user, get_db_session
from dml_bot.api.templating import templates
from dml_bot.bot.formatting import fmt_dt
from dml_bot.config.schema import AppConfig
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.models.user import User
from dml_bot.db.models.watch import WatchSubscription
from dml_bot.services import regulation_service, server_service, watch_service
from dml_bot.utils.time_utils import local_day_range_utc, utc_now

router = APIRouter(prefix="/api/watches")

RANGE_LABELS = {
    "today": "today",
    "week": "the next 7 days",
    "month": "the next 30 days",
    "horizon": "the full booking horizon",
}


def _resolve_range(session: Session, range_key: str, tz_name: str):
    now = utc_now()
    if range_key == "today":
        return local_day_range_utc(now.date(), tz_name)
    if range_key == "week":
        return now, now + timedelta(days=7)
    if range_key == "month":
        return now, now + timedelta(days=30)
    regulation = regulation_service.get_regulation(session)
    return now, now + timedelta(days=regulation.booking_horizon_days)


@router.get("")
async def list_watches(
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
):
    watches = watch_service.list_watches_for_user(session, user.id)
    items = [
        {
            "id": w.id,
            "gpu": w.gpu,
            "range_start_label": fmt_dt(w.range_start, config.bot.timezone),
            "range_end_label": fmt_dt(w.range_end, config.bot.timezone),
            "min_ram_needed_mb": w.min_ram_needed_mb,
        }
        for w in watches
    ]
    return templates.TemplateResponse(request, "partials/watches_list.html", {"watches": items})


@router.get("/new")
async def new_choose_server(
    request: Request, session: Session = Depends(get_db_session), _user=Depends(get_current_user)
):
    servers = server_service.list_servers(session)
    return templates.TemplateResponse(request, "partials/watches_new_servers.html", {"servers": servers})


@router.get("/new/{server_id}")
async def new_choose_gpu(
    server_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    _user=Depends(get_current_user),
):
    server = session.get(Server, server_id)
    gpus = server_service.list_gpus(session, server)
    return templates.TemplateResponse(request, "partials/watches_new_gpus.html", {"server": server, "gpus": gpus})


@router.get("/new/{server_id}/{gpu_id}")
async def new_choose_range(
    server_id: int,
    gpu_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    _user=Depends(get_current_user),
):
    server = session.get(Server, server_id)
    gpu = session.get(GPU, gpu_id)
    return templates.TemplateResponse(
        request,
        "partials/watches_new_range.html",
        {"server": server, "gpu": gpu, "range_labels": RANGE_LABELS},
    )


@router.get("/new/{server_id}/{gpu_id}/{range_key}")
async def new_form(
    server_id: int,
    gpu_id: int,
    range_key: str,
    request: Request,
    session: Session = Depends(get_db_session),
    _user=Depends(get_current_user),
):
    server = session.get(Server, server_id)
    gpu = session.get(GPU, gpu_id)
    return templates.TemplateResponse(
        request, "partials/watches_new_form.html", {"server": server, "gpu": gpu, "range_key": range_key}
    )


@router.post("/new/{server_id}/{gpu_id}/{range_key}")
async def create(
    server_id: int,
    gpu_id: int,
    range_key: str,
    request: Request,
    min_ram_needed_mb: int = Form(...),
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
):
    gpu = session.get(GPU, gpu_id)
    range_start, range_end = _resolve_range(session, range_key, config.bot.timezone)
    watch_service.create_watch(session, user, gpu, range_start, range_end, min_ram_needed_mb)
    return templates.TemplateResponse(request, "partials/watches_created.html", {})


@router.post("/{watch_id}/cancel")
async def cancel(
    watch_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    watch = session.get(WatchSubscription, watch_id)
    if watch is None or watch.user_id != user.id:
        raise HTTPException(status_code=404)
    watch_service.cancel_watch(session, watch)
    return templates.TemplateResponse(request, "partials/watches_cancelled.html", {})
