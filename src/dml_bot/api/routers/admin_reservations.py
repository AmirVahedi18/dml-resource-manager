from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from dml_bot.api.deps import get_app_config, get_db_session, require_admin
from dml_bot.api.templating import templates
from dml_bot.bot.formatting import fmt_dt, fmt_ram
from dml_bot.config.schema import AppConfig
from dml_bot.db.models.reservation import Reservation
from dml_bot.services import regulation_service, reservation_service, usage_service
from dml_bot.utils.time_utils import utc_now

router = APIRouter(prefix="/api/admin/reservations")


@router.get("")
async def list_all(
    request: Request,
    session: Session = Depends(get_db_session),
    _admin=Depends(require_admin),
    config: AppConfig = Depends(get_app_config),
):
    regulation = regulation_service.get_regulation(session)
    now = utc_now()
    reservations = usage_service.get_reservations_in_range(
        session, now, now + timedelta(days=regulation.booking_horizon_days)
    )
    reservations.sort(key=lambda r: r.start_time)
    items = [
        {
            "id": r.id,
            "gpu": r.gpu,
            "user": r.user,
            "start_label": fmt_dt(r.start_time, config.bot.timezone),
        }
        for r in reservations
    ]
    return templates.TemplateResponse(request, "partials/admin_reservations_list.html", {"reservations": items})


@router.get("/{reservation_id}")
async def detail(
    reservation_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    _admin=Depends(require_admin),
    config: AppConfig = Depends(get_app_config),
):
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404)
    summary = (
        f"{reservation.gpu.server.name} GPU{reservation.gpu.index_on_server}<br>"
        f"Student: {reservation.user.full_name}<br>"
        f"{fmt_dt(reservation.start_time, config.bot.timezone)} → "
        f"{fmt_dt(reservation.end_time, config.bot.timezone)}<br>"
        f"RAM: {fmt_ram(reservation.ram_mb)}"
    )
    return templates.TemplateResponse(
        request, "partials/admin_reservations_detail.html", {"reservation": reservation, "summary": summary}
    )


@router.post("/{reservation_id}/cancel")
async def cancel(
    reservation_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    _admin=Depends(require_admin),
):
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404)
    reservation_service.cancel_reservation(session, reservation)
    return templates.TemplateResponse(request, "partials/admin_reservations_cancelled.html", {})
