from datetime import timedelta

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.reservation import Reservation, ReservationStatus
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, user_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.conftest import auth_headers


def _make_reservation(gpu_id, telegram_id, ram_mb=4096):
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=3)
    end = start + timedelta(hours=1)
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation = reservation_service.create_reservation(session, user, gpu, start, end, ram_mb, regulation)
        return reservation.id


def test_list_and_cancel_own_reservation(api_client, lab_setup):
    headers = auth_headers(lab_setup["telegram_id"])
    reservation_id = _make_reservation(lab_setup["gpu_id"], lab_setup["telegram_id"])

    list_resp = api_client.get("/api/reservations", headers=headers)
    assert list_resp.status_code == 200
    assert "lab-server-1" in list_resp.text
    assert "GPU0" in list_resp.text

    detail_resp = api_client.get(f"/api/reservations/{reservation_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert "Cancel this reservation" in detail_resp.text

    cancel_resp = api_client.post(f"/api/reservations/{reservation_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert "cancelled" in cancel_resp.text

    with session_scope() as session:
        reservation = session.get(Reservation, reservation_id)
    assert reservation.status == ReservationStatus.CANCELLED


def test_cannot_cancel_another_users_reservation(api_client, lab_setup):
    reservation_id = _make_reservation(lab_setup["gpu_id"], lab_setup["telegram_id"])

    with session_scope() as session:
        user_service.register_user(session, telegram_id=777, full_name="Mallory")

    other_headers = auth_headers(777)
    detail_resp = api_client.get(f"/api/reservations/{reservation_id}", headers=other_headers)
    assert detail_resp.status_code == 404

    cancel_resp = api_client.post(f"/api/reservations/{reservation_id}/cancel", headers=other_headers)
    assert cancel_resp.status_code == 404

    with session_scope() as session:
        reservation = session.get(Reservation, reservation_id)
    assert reservation.status == ReservationStatus.ACTIVE
