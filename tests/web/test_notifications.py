from tests.web.conftest import login


def test_no_notifications_by_default(client, student_with_access):
    headers = login(client, "stud1", "studpass123")
    r = client.get("/api/notifications", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_deactivating_a_server_notifies_users_with_access(client, admin_headers, db_session, student_with_access, server_and_gpu):
    server, _ = server_and_gpu
    headers = login(client, "stud1", "studpass123")

    r = client.patch(f"/api/admin/servers/{server.id}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 200

    r = client.get("/api/notifications", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert "deactivated" in body[0]["message"]


def test_dismiss_notification(client, admin_headers, db_session, student_with_access, server_and_gpu):
    server, _ = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    client.patch(f"/api/admin/servers/{server.id}/active", headers=admin_headers, json={"is_active": False})

    notification_id = client.get("/api/notifications", headers=headers).json()[0]["id"]
    r = client.post(f"/api/notifications/{notification_id}/dismiss", headers=headers)
    assert r.status_code == 204

    assert client.get("/api/notifications", headers=headers).json() == []


def test_dismiss_other_users_notification_returns_404(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_core.services import auth_service

    server, _ = server_and_gpu
    auth_service.create_user_with_credentials(db_session, "other1", "otherpass123", "Other One")
    db_session.commit()
    client.patch(f"/api/admin/servers/{server.id}/active", headers=admin_headers, json={"is_active": False})

    headers = login(client, "stud1", "studpass123")
    notification_id = client.get("/api/notifications", headers=headers).json()[0]["id"]

    other_headers = login(client, "other1", "otherpass123")
    r = client.post(f"/api/notifications/{notification_id}/dismiss", headers=other_headers)
    assert r.status_code == 404


def test_reactivating_a_gpu_resumes_reservation_and_notifies(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from datetime import datetime, timedelta, timezone

    from dml_core.services import regulation_service, reservation_service

    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")

    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=2)
    reservation = reservation_service.create_reservation(
        db_session, student_with_access, gpu, start, end, 4096, regulation, description="training run"
    )
    db_session.commit()

    client.patch(f"/api/admin/gpus/{gpu.id}/active", headers=admin_headers, json={"is_active": False})
    r = client.get("/api/reservations", headers=headers)
    assert r.json()[0]["status"] == "SUSPENDED"

    client.patch(f"/api/admin/gpus/{gpu.id}/active", headers=admin_headers, json={"is_active": True})
    r = client.get("/api/reservations", headers=headers)
    assert r.json()[0]["status"] == "ACTIVE"

    notifications = client.get("/api/notifications", headers=headers).json()
    assert len(notifications) == 2
    assert "resumed" in notifications[-1]["message"]
