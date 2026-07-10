from datetime import datetime, timedelta, timezone

from tests.web.conftest import login


def _future_slot(hours_from_now=1, duration_hours=2):
    start = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).replace(
        minute=0, second=0, microsecond=0
    )
    end = start + timedelta(hours=duration_hours)
    return start.isoformat(), end.isoformat()


def test_create_reservation_requires_server_access(client, student_user, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_slot()
    r = client.post(
        "/api/reservations", headers=headers, json={"gpu_id": gpu.id, "start_time": start, "end_time": end, "ram_mb": 4096}
    )
    assert r.status_code == 403


def test_create_list_cancel_reservation(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_slot()

    r = client.post(
        "/api/reservations", headers=headers, json={"gpu_id": gpu.id, "start_time": start, "end_time": end, "ram_mb": 4096}
    )
    assert r.status_code == 201, r.text
    reservation_id = r.json()["id"]

    r = client.get("/api/reservations", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == reservation_id

    r = client.delete(f"/api/reservations/{reservation_id}", headers=headers)
    assert r.status_code == 204

    assert client.get("/api/reservations", headers=headers).json() == []


def test_create_reservation_exceeding_ram_returns_422(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_slot()
    r = client.post(
        "/api/reservations",
        headers=headers,
        json={"gpu_id": gpu.id, "start_time": start, "end_time": end, "ram_mb": 999_999},
    )
    assert r.status_code == 422
    assert "ram_mb" in r.json()["detail"]


def test_create_reservation_unaligned_slot_returns_422(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start_dt = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=7, second=0, microsecond=0)
    end_dt = start_dt + timedelta(hours=1)
    r = client.post(
        "/api/reservations",
        headers=headers,
        json={"gpu_id": gpu.id, "start_time": start_dt.isoformat(), "end_time": end_dt.isoformat(), "ram_mb": 4096},
    )
    assert r.status_code == 422


def test_cancel_other_users_reservation_returns_404(client, db_session, student_with_access, server_and_gpu):
    from dml_core.services import auth_service, reservation_service, regulation_service

    _, gpu = server_and_gpu
    other = auth_service.create_user_with_credentials(db_session, "other1", "otherpass123", "Other One")
    db_session.commit()
    regulation = regulation_service.get_regulation(db_session)
    start_dt = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    reservation = reservation_service.create_reservation(
        db_session, other, gpu, start_dt, start_dt + timedelta(hours=1), 4096, regulation
    )
    db_session.commit()

    headers = login(client, "stud1", "studpass123")
    r = client.delete(f"/api/reservations/{reservation.id}", headers=headers)
    assert r.status_code == 404
