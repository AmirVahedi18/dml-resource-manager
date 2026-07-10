from datetime import datetime, timedelta, timezone

from tests.web.conftest import login


def test_regulation_includes_app_timezone(client, admin_headers):
    r = client.get("/api/regulation", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["timezone"] == "UTC"


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


def test_availability_chart_shape(client, admin_headers, db_session, server_and_gpu):
    from dml_bot.services import auth_service, reservation_service, regulation_service

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
        params={"range_start": range_start.isoformat(), "range_end": range_end.isoformat(), "bucket_hours": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["capacity_mb"] == gpu.total_ram_mb
    assert len(body["segments"]) == 1
    assert body["segments"][0]["user"] == "Chart User"
    assert any(b["usage"] for b in body["buckets"])
