from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from dml_core.db.models.reservation import Reservation
from dml_core.db.models.user import User
from dml_core.services import regulation_service, reservation_service, usage_service
from dml_core.utils.time_utils import utc_now
from dml_web.deps import get_session, require_admin
from dml_web.schemas.admin_reservations import (
    AdminReservationListOut,
    AdminReservationOut,
    BulkCancelResult,
    CancelAllRequest,
)

router = APIRouter()

LAB_WIDE_CONFIRM_PHRASE = "CANCEL ALL"


def _to_admin_out(r: Reservation) -> AdminReservationOut:
    return AdminReservationOut(
        id=r.id,
        gpu_id=r.gpu_id,
        user_id=r.user_id,
        user_full_name=r.user.full_name,
        server_name=r.gpu.server.name,
        gpu_index=r.gpu.index_on_server,
        start_time=r.start_time,
        end_time=r.end_time,
        ram_mb=r.ram_mb,
        description=r.description,
        status=r.status.value,
    )


@router.get("", response_model=AdminReservationListOut)
def list_reservations(
    user_id: int | None = None,
    gpu_id: int | None = None,
    server_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> AdminReservationListOut:
    regulation = regulation_service.get_regulation(session)
    now = utc_now()
    range_end = now + timedelta(days=regulation.booking_horizon_days)
    total = usage_service.count_reservations_in_range(
        session, now, range_end, user_id=user_id, gpu_id=gpu_id, server_id=server_id, include_suspended=True
    )
    reservations = usage_service.get_reservations_in_range(
        session,
        now,
        range_end,
        user_id=user_id,
        gpu_id=gpu_id,
        server_id=server_id,
        limit=page_size,
        offset=(page - 1) * page_size,
        include_suspended=True,
    )
    return AdminReservationListOut(
        items=[_to_admin_out(r) for r in reservations], total=total, page=page, page_size=page_size
    )


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_reservation(
    reservation_id: int, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> None:
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")
    reservation_service.cancel_reservation(session, reservation)


@router.post("/cancel-for-user/{user_id}", response_model=BulkCancelResult)
def cancel_for_user(
    user_id: int, session: Session = Depends(get_session), _: User = Depends(require_admin)
) -> BulkCancelResult:
    reservations = reservation_service.list_active_reservations_for_user(session, user_id)
    count = reservation_service.cancel_reservations(session, reservations)
    return BulkCancelResult(cancelled=count)


@router.post("/cancel-all", response_model=BulkCancelResult)
def cancel_all(
    payload: CancelAllRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> BulkCancelResult:
    if payload.confirm_phrase.strip() != LAB_WIDE_CONFIRM_PHRASE:
        raise HTTPException(422, f"Type '{LAB_WIDE_CONFIRM_PHRASE}' exactly to confirm.")
    regulation = regulation_service.get_regulation(session)
    now = utc_now()
    reservations = usage_service.get_reservations_in_range(
        session, now, now + timedelta(days=regulation.booking_horizon_days), include_suspended=True
    )
    count = reservation_service.cancel_reservations(session, reservations, now=now)
    return BulkCancelResult(cancelled=count)
