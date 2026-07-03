from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.reservation import Reservation, ReservationStatus
from dml_bot.utils.time_utils import to_naive_utc


def get_reservations_in_range(
    session: Session,
    range_start: datetime,
    range_end: datetime,
    *,
    user_id: int | None = None,
    gpu_id: int | None = None,
    server_id: int | None = None,
) -> list[Reservation]:
    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    stmt = select(Reservation).where(
        Reservation.status == ReservationStatus.ACTIVE,
        Reservation.start_time < range_end,
        Reservation.end_time > range_start,
    )
    if user_id is not None:
        stmt = stmt.where(Reservation.user_id == user_id)
    if gpu_id is not None:
        stmt = stmt.where(Reservation.gpu_id == gpu_id)
    if server_id is not None:
        stmt = stmt.join(GPU, Reservation.gpu_id == GPU.id).where(GPU.server_id == server_id)
    return list(session.execute(stmt).scalars().all())


def _clipped_hours(reservation: Reservation, range_start: datetime, range_end: datetime) -> float:
    start = max(reservation.start_time, range_start)
    end = min(reservation.end_time, range_end)
    return max((end - start).total_seconds() / 3600, 0.0)


def total_gpu_hours_by_user(
    reservations: list[Reservation], range_start: datetime, range_end: datetime
) -> dict[int, float]:
    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    totals: dict[int, float] = {}
    for r in reservations:
        totals[r.user_id] = totals.get(r.user_id, 0.0) + _clipped_hours(r, range_start, range_end)
    return totals


def total_ram_hours_by_gpu(
    reservations: list[Reservation], range_start: datetime, range_end: datetime
) -> dict[int, float]:
    range_start, range_end = to_naive_utc(range_start), to_naive_utc(range_end)
    totals: dict[int, float] = {}
    for r in reservations:
        hours = _clipped_hours(r, range_start, range_end)
        totals[r.gpu_id] = totals.get(r.gpu_id, 0.0) + hours * r.ram_mb
    return totals
