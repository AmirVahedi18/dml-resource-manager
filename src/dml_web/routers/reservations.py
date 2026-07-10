from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dml_bot.db.models.reservation import Reservation
from dml_bot.db.models.user import User
from dml_bot.services import regulation_service, reservation_service, server_service
from dml_web import access
from dml_web.deps import get_current_user, get_session
from dml_web.schemas.reservations import ReservationCreate, ReservationOut

router = APIRouter()


@router.get("", response_model=list[ReservationOut])
def list_my_reservations(
    upcoming_only: bool = True,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[Reservation]:
    return reservation_service.list_active_reservations_for_user(session, user.id, upcoming_only=upcoming_only)


@router.post("", response_model=ReservationOut, status_code=status.HTTP_201_CREATED)
def create_reservation(
    payload: ReservationCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Reservation:
    gpu = server_service.get_gpu(session, payload.gpu_id)
    if gpu is None:
        raise HTTPException(404, "GPU not found")
    access.ensure_gpu_access(session, user, gpu)

    regulation = regulation_service.get_regulation(session)
    return reservation_service.create_reservation(
        session, user, gpu, payload.start_time, payload.end_time, payload.ram_mb, regulation
    )


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_reservation(
    reservation_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    reservation = session.get(Reservation, reservation_id)
    if reservation is None or reservation.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")
    regulation = regulation_service.get_regulation(session)
    reservation_service.assert_cancellable(reservation, regulation)
    reservation_service.cancel_reservation(session, reservation)
