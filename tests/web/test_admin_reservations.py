from datetime import datetime, timedelta, timezone


def _make_reservation(db_session, user, gpu, hours_from_now=1, duration_hours=2, ram_mb=4096):
    from dml_bot.services import reservation_service, regulation_service

    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).replace(
        minute=0, second=0, microsecond=0, tzinfo=None
    )
    end = start + timedelta(hours=duration_hours)
    reservation = reservation_service.create_reservation(db_session, user, gpu, start, end, ram_mb, regulation)
    db_session.commit()
    return reservation


def test_list_all_reservations(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu)

    r = client.get("/api/admin/reservations", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["user_full_name"] == "Student One"
    assert body[0]["server_name"] == "srv-1"


def test_list_reservations_by_user(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu)

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"user_id": student_with_access.id})
    assert len(r.json()) == 1

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"user_id": 999999})
    assert r.json() == []


def test_admin_cancel_single_reservation(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    reservation = _make_reservation(db_session, student_with_access, gpu)

    r = client.delete(f"/api/admin/reservations/{reservation.id}", headers=admin_headers)
    assert r.status_code == 204
    assert client.get("/api/admin/reservations", headers=admin_headers).json() == []


def test_admin_cancel_bypasses_cancellation_cutoff(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_bot.services import regulation_service

    _, gpu = server_and_gpu
    regulation_service.update_regulation(db_session, updated_by=1, min_cancellation_notice_minutes=1440)
    db_session.commit()
    reservation = _make_reservation(db_session, student_with_access, gpu)

    r = client.delete(f"/api/admin/reservations/{reservation.id}", headers=admin_headers)
    assert r.status_code == 204


def test_cancel_for_user(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu, hours_from_now=1)
    _make_reservation(db_session, student_with_access, gpu, hours_from_now=5)

    r = client.post(f"/api/admin/reservations/cancel-for-user/{student_with_access.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["cancelled"] == 2


def test_cancel_all_requires_exact_phrase(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu)

    r = client.post("/api/admin/reservations/cancel-all", headers=admin_headers, json={"confirm_phrase": "nope"})
    assert r.status_code == 422
    assert client.get("/api/admin/reservations", headers=admin_headers).json() != []

    r = client.post("/api/admin/reservations/cancel-all", headers=admin_headers, json={"confirm_phrase": "cancel all"})
    assert r.status_code == 200
    assert r.json()["cancelled"] == 1
