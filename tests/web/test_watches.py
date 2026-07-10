from datetime import datetime, timedelta, timezone

from tests.web.conftest import login


def _future_range(hours_from_now=1, span_hours=10):
    start = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).replace(
        minute=0, second=0, microsecond=0
    )
    end = start + timedelta(hours=span_hours)
    return start.isoformat(), end.isoformat()


def test_create_watch_requires_server_access(client, student_user, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    r = client.post(
        "/api/watches", headers=headers, json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048}
    )
    assert r.status_code == 403


def test_create_watch_is_always_auto_book(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    r = client.post(
        "/api/watches", headers=headers, json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048}
    )
    assert r.status_code == 201, r.text
    assert r.json()["auto_book"] is True


def test_list_and_cancel_watch(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    watch = client.post(
        "/api/watches", headers=headers, json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048}
    ).json()

    r = client.get("/api/watches", headers=headers)
    assert len(r.json()) == 1

    r = client.delete(f"/api/watches/{watch['id']}", headers=headers)
    assert r.status_code == 204
    assert client.get("/api/watches", headers=headers).json() == []


def test_scheduler_autobooks_matching_watch(db_session, student_with_access, server_and_gpu):
    from dml_bot.services import watch_service
    from dml_web.scheduler import run_watch_autobook_check

    _, gpu = server_and_gpu
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=5)
    watch = watch_service.create_watch(db_session, student_with_access, gpu, start, end, 4096, auto_book=True)
    db_session.commit()

    booked = run_watch_autobook_check(db_session)
    db_session.commit()

    assert booked == 1
    remaining = watch_service.list_watches_for_user(db_session, student_with_access.id, active_only=True)
    assert remaining == []
