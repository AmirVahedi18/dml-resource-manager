from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from dml_bot.api.deps import get_app_config, get_current_user, get_db_session
from dml_bot.api.templating import templates
from dml_bot.bot.formatting import fmt_dt, reservation_summary
from dml_bot.config.schema import AppConfig
from dml_bot.db.models.reservation import Reservation
from dml_bot.db.models.user import User
from dml_bot.services import reservation_service

router = APIRouter(prefix="/api/reservations")


@router.get("")
async def list_reservations(
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
):
    reservations = reservation_service.list_active_reservations_for_user(session, user.id)
    items = [
        {"id": r.id, "gpu": r.gpu, "start_label": fmt_dt(r.start_time, config.bot.timezone)}
        for r in reservations
    ]
    return templates.TemplateResponse(request, "partials/reservations_list.html", {"reservations": items})


@router.get("/{reservation_id}")
async def detail(
    reservation_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
):
    reservation = session.get(Reservation, reservation_id)
    if reservation is None or reservation.user_id != user.id:
        raise HTTPException(status_code=404)
    summary = reservation_summary(reservation, reservation.gpu, reservation.gpu.server, config.bot.timezone)
    return templates.TemplateResponse(
        request, "partials/reservations_detail.html", {"reservation": reservation, "summary": summary}
    )


@router.post("/{reservation_id}/cancel")
async def cancel(
    reservation_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    reservation = session.get(Reservation, reservation_id)
    if reservation is None or reservation.user_id != user.id:
        raise HTTPException(status_code=404)
    reservation_service.cancel_reservation(session, reservation)
    return templates.TemplateResponse(request, "partials/reservations_cancelled.html", {})
