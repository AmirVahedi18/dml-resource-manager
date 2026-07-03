import json
from datetime import date as date_cls
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from dml_bot.api.deps import get_app_config, get_current_user, get_db_session
from dml_bot.api.routers._slots import build_day_slots
from dml_bot.api.templating import templates
from dml_bot.bot.formatting import reservation_summary
from dml_bot.config.schema import AppConfig
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.models.user import User
from dml_bot.services import regulation_service, reservation_service, server_service

router = APIRouter(prefix="/api/reserve")


@router.get("")
async def list_servers(
    request: Request, session: Session = Depends(get_db_session), _user=Depends(get_current_user)
):
    servers = server_service.list_servers(session)
    return templates.TemplateResponse(request, "partials/reserve_servers.html", {"servers": servers})


@router.get("/{server_id}")
async def list_gpus(
    server_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    _user=Depends(get_current_user),
):
    server = session.get(Server, server_id)
    gpus = server_service.list_gpus(session, server)
    return templates.TemplateResponse(request, "partials/reserve_gpus.html", {"server": server, "gpus": gpus})


@router.get("/{server_id}/{gpu_id}")
async def pick_date(
    server_id: int,
    gpu_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    _user=Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
):
    server = session.get(Server, server_id)
    gpu = session.get(GPU, gpu_id)
    days = [date_cls.today() + timedelta(days=i) for i in range(config.bot.date_picker_days_visible)]
    return templates.TemplateResponse(
        request, "partials/reserve_dates.html", {"server": server, "gpu": gpu, "days": days}
    )


@router.get("/{server_id}/{gpu_id}/{day}")
async def show_grid(
    server_id: int,
    gpu_id: int,
    day: date_cls,
    request: Request,
    session: Session = Depends(get_db_session),
    _user=Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
):
    server = session.get(Server, server_id)
    gpu = session.get(GPU, gpu_id)
    slots = build_day_slots(session, gpu, day, config.bot.timezone)
    return templates.TemplateResponse(
        request,
        "partials/reserve_grid.html",
        {"server": server, "gpu": gpu, "slots_json": json.dumps(slots)},
    )


@router.post("/{server_id}/{gpu_id}")
async def create(
    server_id: int,
    gpu_id: int,
    request: Request,
    start: datetime = Form(...),
    end: datetime = Form(...),
    ram_mb: int = Form(...),
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
):
    server = session.get(Server, server_id)
    gpu = session.get(GPU, gpu_id)
    regulation = regulation_service.get_regulation(session)

    try:
        reservation = reservation_service.create_reservation(session, user, gpu, start, end, ram_mb, regulation)
    except reservation_service.ReservationError as exc:
        return templates.TemplateResponse(request, "partials/reserve_result.html", {"error": str(exc)})

    summary = reservation_summary(reservation, gpu, server, config.bot.timezone)
    return templates.TemplateResponse(request, "partials/reserve_result.html", {"summary": summary})
