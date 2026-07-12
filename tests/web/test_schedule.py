from datetime import datetime, timedelta, timezone

from tests.web.conftest import login


def test_regulation_includes_app_timezone(client, admin_headers):
    r = client.get("/api/regulation", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["timezone"] == "UTC"
    assert r.json()["reactivation_delay_minutes"] == 60


def test_servers_filtered_by_access_for_student(client, student_user, server_and_gpu):
    headers = login(client, "stud1", "studpass123")
    assert client.get("/api/servers", headers=headers).json() == []


def test_servers_unrestricted_for_admin(client, admin_headers, server_and_gpu):
    server, _ = server_and_gpu
    servers = client.get("/api/servers", headers=admin_headers).json()
    assert [s["id"] for s in servers] == [server.id]


def test_gpus_for_server_requires_access(client, student_user, server_and_gpu):
    server, _ = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    assert client.get(f"/api/servers/{server.id}/gpus", headers=headers).status_code == 403


def test_inactive_server_and_gpu_still_visible_to_student_with_access(
    client, student_with_access, server_and_gpu
):
    from dml_core.services import server_service

    server, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")

    servers = client.get("/api/servers", headers=headers).json()
    assert [s["is_active"] for s in servers if s["id"] == server.id] == [True]

    gpus = client.get(f"/api/servers/{server.id}/gpus", headers=headers).json()
    assert [g["is_active"] for g in gpus if g["id"] == gpu.id] == [True]

    overview = client.get("/api/overview", headers=headers).json()
    assert overview[0]["is_active"] is True
    assert overview[0]["gpus"][0]["is_active"] is True


def test_deactivated_server_and_gpu_still_visible_but_marked_inactive(
    client, db_session, student_with_access, server_and_gpu
):
    from dml_core.services import server_service

    server, gpu = server_and_gpu
    server_service.set_gpu_active(db_session, gpu, False)
    db_session.commit()
    headers = login(client, "stud1", "studpass123")

    gpus = client.get(f"/api/servers/{server.id}/gpus", headers=headers).json()
    assert gpus == [{"id": gpu.id, "server_id": server.id, "index_on_server": 0, "model_name": "A100", "total_ram_mb": 40960, "is_active": False}]

    overview = client.get("/api/overview", headers=headers).json()
    assert overview[0]["gpus"][0]["is_active"] is False

    server_service.set_server_active(db_session, server, False)
    db_session.commit()
    servers = client.get("/api/servers", headers=headers).json()
    assert [s["is_active"] for s in servers if s["id"] == server.id] == [False]
    overview = client.get("/api/overview", headers=headers).json()
    assert overview[0]["is_active"] is False


def test_availability_chart_shape(client, admin_headers, db_session, server_and_gpu):
    from dml_core.services import auth_service, reservation_service, regulation_service

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    student = auth_service.create_user_with_credentials(db_session, "chartuser", "chartpass123", "Chart User")
    db_session.commit()
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=2)
    reservation_service.create_reservation(db_session, student, gpu, start, end, 4096, regulation)
    db_session.commit()

    range_start = start - timedelta(hours=1)
    range_end = end + timedelta(hours=1)
    r = client.get(
        f"/api/gpus/{gpu.id}/availability",
        headers=admin_headers,
        params={"range_start": range_start.isoformat(), "range_end": range_end.isoformat()},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["capacity_mb"] == gpu.total_ram_mb
    assert body["bucket_minutes"] == regulation.min_reservation_slot_minutes
    assert len(body["segments"]) == 1
    assert body["segments"][0]["user"] == "Chart User"
    assert any(b["usage"] for b in body["buckets"])


def test_free_ram_reflects_overlapping_reservation(client, admin_headers, db_session, server_and_gpu):
    from dml_core.services import auth_service, reservation_service, regulation_service

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    student = auth_service.create_user_with_credentials(db_session, "freeramuser", "freerampass123", "Free Ram User")
    db_session.commit()
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=2)
    reservation_service.create_reservation(db_session, student, gpu, start, end, 4096, regulation)
    db_session.commit()

    r = client.get(
        f"/api/gpus/{gpu.id}/free-ram",
        headers=admin_headers,
        params={"start": start.isoformat(), "end": end.isoformat()},
    )
    assert r.status_code == 200
    assert r.json()["free_ram_mb"] == gpu.total_ram_mb - 4096

    # A window with no overlap at all is fully free.
    later_start = end + timedelta(hours=5)
    later_end = later_start + timedelta(hours=1)
    r = client.get(
        f"/api/gpus/{gpu.id}/free-ram",
        headers=admin_headers,
        params={"start": later_start.isoformat(), "end": later_end.isoformat()},
    )
    assert r.json()["free_ram_mb"] == gpu.total_ram_mb


def test_free_ram_requires_access(client, student_user, server_and_gpu):
    server, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start = datetime.now(timezone.utc).replace(tzinfo=None)
    end = start + timedelta(hours=1)
    r = client.get(
        f"/api/gpus/{gpu.id}/free-ram",
        headers=headers,
        params={"start": start.isoformat(), "end": end.isoformat()},
    )
    assert r.status_code == 403
