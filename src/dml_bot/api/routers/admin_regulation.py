from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from dml_bot.api.auth import TelegramWebAppUser
from dml_bot.api.deps import get_db_session, require_admin
from dml_bot.api.templating import templates
from dml_bot.services import regulation_service

router = APIRouter(prefix="/api/admin/regulation")

FIELD_LABELS = {
    "max_ram_per_reservation_mb": "Max RAM per reservation (MB)",
    "max_duration_hours": "Max duration per reservation (hours)",
    "booking_horizon_days": "Booking horizon (days ahead)",
    "min_reservation_slot_minutes": "Time slot size (minutes)",
    "max_active_reservations_per_user": "Max active reservations per user",
}


def _render_menu(request: Request, session: Session):
    regulation = regulation_service.get_regulation(session)
    fields = [(key, label, getattr(regulation, key)) for key, label in FIELD_LABELS.items()]
    return templates.TemplateResponse(request, "partials/admin_regulation_menu.html", {"fields": fields})


@router.get("")
async def menu(request: Request, session: Session = Depends(get_db_session), _admin=Depends(require_admin)):
    return _render_menu(request, session)


@router.get("/{field}")
async def edit_form(
    field: str, request: Request, session: Session = Depends(get_db_session), _admin=Depends(require_admin)
):
    if field not in FIELD_LABELS:
        raise HTTPException(status_code=404)
    regulation = regulation_service.get_regulation(session)
    return templates.TemplateResponse(
        request,
        "partials/admin_regulation_edit.html",
        {"field": field, "label": FIELD_LABELS[field], "current_value": getattr(regulation, field)},
    )


@router.post("/{field}")
async def update(
    field: str,
    request: Request,
    value: int = Form(...),
    session: Session = Depends(get_db_session),
    admin: TelegramWebAppUser = Depends(require_admin),
):
    if field not in FIELD_LABELS:
        raise HTTPException(status_code=404)
    regulation_service.update_regulation(session, admin.id, **{field: value})
    return _render_menu(request, session)
