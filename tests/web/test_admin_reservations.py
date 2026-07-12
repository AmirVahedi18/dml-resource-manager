from datetime import datetime, timedelta, timezone


def _make_reservation(db_session, user, gpu, hours_from_now=1, duration_hours=2, ram_mb=4096, description=""):
    from dml_core.services import reservation_service, regulation_service

    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).replace(
        minute=0, second=0, microsecond=0, tzinfo=None
    )
    end = start + timedelta(hours=duration_hours)
    reservation = reservation_service.create_reservation(
        db_session, user, gpu, start, end, ram_mb, regulation, description=description
    )
    db_session.commit()
    return reservation


def test_list_all_reservations(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu)

    r = client.get("/api/admin/reservations", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["user_full_name"] == "Student One"
    assert body["items"][0]["server_name"] == "srv-1"


def test_admin_sees_reservation_description(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu, description="NeurIPS ablations")

    r = client.get("/api/admin/reservations", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["items"][0]["description"] == "NeurIPS ablations"


def test_list_reservations_by_gpu_and_server(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_core.services import server_service

    server1, gpu1 = server_and_gpu
    server2 = server_service.create_server(db_session, "srv-2")
    gpu2 = server_service.add_gpu(db_session, server2, 0, "A100", 40960)
    db_session.commit()

    _make_reservation(db_session, student_with_access, gpu1, hours_from_now=1)
    _make_reservation(db_session, student_with_access, gpu2, hours_from_now=5)

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"gpu_id": gpu1.id})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["gpu_id"] == gpu1.id

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"server_id": server2.id})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["gpu_id"] == gpu2.id

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"server_id": server1.id})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["gpu_id"] == gpu1.id


def test_list_reservations_by_user(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu)

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"user_id": student_with_access.id})
    assert r.json()["total"] == 1

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"user_id": 999999})
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_admin_cancel_single_reservation(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    reservation = _make_reservation(db_session, student_with_access, gpu)

    r = client.delete(f"/api/admin/reservations/{reservation.id}", headers=admin_headers)
    assert r.status_code == 204
    assert client.get("/api/admin/reservations", headers=admin_headers).json()["items"] == []


def test_list_reservations_paginated(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_core.services import auth_service

    _, gpu = server_and_gpu
    users = [student_with_access] + [
        auth_service.create_user_with_credentials(db_session, f"stud{i}", "studpass123", f"Student {i}")
        for i in range(2, 6)
    ]
    db_session.commit()
    for i, user in enumerate(users):
        _make_reservation(db_session, user, gpu, hours_from_now=1 + i * 3)

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"page": 3, "page_size": 2})
    body = r.json()
    assert len(body["items"]) == 1

    r = client.get("/api/admin/reservations", headers=admin_headers, params={"page": 4, "page_size": 2})
    assert r.json()["items"] == []

    all_ids = set()
    for page in (1, 2, 3):
        page_ids = [item["id"] for item in client.get(
            "/api/admin/reservations", headers=admin_headers, params={"page": page, "page_size": 2}
        ).json()["items"]]
        all_ids.update(page_ids)
    assert len(all_ids) == 5


def test_cancel_for_user(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu, hours_from_now=1)
    _make_reservation(db_session, student_with_access, gpu, hours_from_now=5)

    r = client.post(f"/api/admin/reservations/cancel-for-user/{student_with_access.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["cancelled"] == 2


def test_list_reservations_shows_suspended(client, admin_headers, db_session, student_with_access, server_and_gpu):
    server, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu)

    r = client.patch(f"/api/admin/gpus/{gpu.id}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 200

    r = client.get("/api/admin/reservations", headers=admin_headers)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["status"] == "SUSPENDED"


def test_cancel_all_requires_exact_phrase(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_reservation(db_session, student_with_access, gpu)

    r = client.post("/api/admin/reservations/cancel-all", headers=admin_headers, json={"confirm_phrase": "nope"})
    assert r.status_code == 422
    assert client.get("/api/admin/reservations", headers=admin_headers).json()["items"] != []

    r = client.post("/api/admin/reservations/cancel-all", headers=admin_headers, json={"confirm_phrase": "cancel all"})
    assert r.status_code == 422
    assert client.get("/api/admin/reservations", headers=admin_headers).json()["items"] != []

    r = client.post("/api/admin/reservations/cancel-all", headers=admin_headers, json={"confirm_phrase": "  CANCEL ALL  "})
    assert r.status_code == 200
    assert r.json()["cancelled"] == 1
