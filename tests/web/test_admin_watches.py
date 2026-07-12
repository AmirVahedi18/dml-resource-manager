from datetime import datetime, timedelta, timezone


def _make_watch(db_session, user, gpu, hours_from_now=1, span_hours=5, min_ram_needed_mb=2048, description=""):
    from dml_core.services import regulation_service, watch_service

    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).replace(
        minute=0, second=0, microsecond=0, tzinfo=None
    )
    end = start + timedelta(hours=span_hours)
    watch = watch_service.create_watch(
        db_session, user, gpu, start, end, min_ram_needed_mb, regulation, auto_book=True, description=description
    )
    db_session.commit()
    return watch


def test_list_all_watches(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_watch(db_session, student_with_access, gpu)

    r = client.get("/api/admin/watches", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["user_full_name"] == "Student One"
    assert body["items"][0]["server_name"] == "srv-1"
    assert body["items"][0]["status"] == "active"


def test_admin_sees_watch_description(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_watch(db_session, student_with_access, gpu, description="NeurIPS ablations")

    r = client.get("/api/admin/watches", headers=admin_headers)
    assert r.json()["items"][0]["description"] == "NeurIPS ablations"


def test_list_watches_by_gpu_and_server(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_core.services import server_service

    server1, gpu1 = server_and_gpu
    server2 = server_service.create_server(db_session, "srv-2")
    gpu2 = server_service.add_gpu(db_session, server2, 0, "A100", 40960)
    db_session.commit()

    _make_watch(db_session, student_with_access, gpu1, hours_from_now=1)
    _make_watch(db_session, student_with_access, gpu2, hours_from_now=8)

    r = client.get("/api/admin/watches", headers=admin_headers, params={"gpu_id": gpu1.id})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["gpu_id"] == gpu1.id

    r = client.get("/api/admin/watches", headers=admin_headers, params={"server_id": server2.id})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["gpu_id"] == gpu2.id

    r = client.get("/api/admin/watches", headers=admin_headers, params={"server_id": server1.id})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["gpu_id"] == gpu1.id


def test_list_watches_by_user(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    _make_watch(db_session, student_with_access, gpu)

    r = client.get("/api/admin/watches", headers=admin_headers, params={"user_id": student_with_access.id})
    assert r.json()["total"] == 1

    r = client.get("/api/admin/watches", headers=admin_headers, params={"user_id": 999999})
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_admin_cancel_single_watch(client, admin_headers, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    watch = _make_watch(db_session, student_with_access, gpu)

    r = client.delete(f"/api/admin/watches/{watch.id}", headers=admin_headers)
    assert r.status_code == 204

    body = client.get("/api/admin/watches", headers=admin_headers).json()
    assert body["items"][0]["status"] == "cancelled"


def test_admin_cancel_missing_watch_returns_404(client, admin_headers):
    r = client.delete("/api/admin/watches/999999", headers=admin_headers)
    assert r.status_code == 404


def test_list_watches_shows_matched_status(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_web.scheduler import run_watch_autobook_check

    _, gpu = server_and_gpu
    watch = _make_watch(db_session, student_with_access, gpu, min_ram_needed_mb=4096)

    booked = run_watch_autobook_check(db_session)
    db_session.commit()
    assert booked == 1

    r = client.get("/api/admin/watches", headers=admin_headers)
    body = r.json()
    assert body["items"][0]["id"] == watch.id
    assert body["items"][0]["status"] == "matched"


def test_list_watches_paginated(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_core.services import auth_service

    _, gpu = server_and_gpu
    users = [student_with_access] + [
        auth_service.create_user_with_credentials(db_session, f"stud{i}", "studpass123", f"Student {i}")
        for i in range(2, 6)
    ]
    db_session.commit()
    for i, user in enumerate(users):
        _make_watch(db_session, user, gpu, hours_from_now=1 + i * 6)

    r = client.get("/api/admin/watches", headers=admin_headers, params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2

    r = client.get("/api/admin/watches", headers=admin_headers, params={"page": 3, "page_size": 2})
    assert len(r.json()["items"]) == 1

    r = client.get("/api/admin/watches", headers=admin_headers, params={"page": 4, "page_size": 2})
    assert r.json()["items"] == []

    all_ids = set()
    for page in (1, 2, 3):
        page_ids = [item["id"] for item in client.get(
            "/api/admin/watches", headers=admin_headers, params={"page": page, "page_size": 2}
        ).json()["items"]]
        all_ids.update(page_ids)
    assert len(all_ids) == 5


def test_non_admin_cannot_list_watches(client, db_session, student_with_access):
    from tests.web.conftest import login

    headers = login(client, "stud1", "studpass123")
    r = client.get("/api/admin/watches", headers=headers)
    assert r.status_code == 403
