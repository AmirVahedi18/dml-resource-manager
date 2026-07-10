from datetime import datetime, timedelta, timezone

from tests.factories import make_user
from tests.web.conftest import login


def _future_range(hours_from_now=1, span_hours=10):
    start = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).replace(
        minute=0, second=0, microsecond=0
    )
    end = start + timedelta(hours=span_hours)
    return start.isoformat(), end.isoformat()


def _occupy(db_session, gpu, start, end, telegram_id_start=900):
    """Books enough of `gpu`, overlapping a single aligned slot at `start`, that it has no free
    RAM left there -- so `min_free_ram_in_range` reports 0 somewhere inside [start, end) and a
    watch can be created for that window (watch creation is rejected when the GPU already has
    enough free RAM). Splits across multiple occupiers since a single reservation is capped at
    the regulation's max_ram_per_reservation_mb, which can be well under the GPU's total RAM."""
    from dml_bot.services import regulation_service, reservation_service

    regulation = regulation_service.get_regulation(db_session)
    slot = timedelta(minutes=regulation.min_reservation_slot_minutes)
    occupied_start = datetime.fromisoformat(start)
    occupied_end = occupied_start + slot

    reservations = []
    remaining = gpu.total_ram_mb
    tid = telegram_id_start
    while remaining > 0:
        chunk = min(remaining, regulation.max_ram_per_reservation_mb)
        occupier = make_user(db_session, telegram_id=tid)
        tid += 1
        reservations.append(
            reservation_service.create_reservation(db_session, occupier, gpu, occupied_start, occupied_end, chunk, regulation)
        )
        remaining -= chunk
    db_session.commit()
    return reservations


def test_create_watch_requires_server_access(client, student_user, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    r = client.post(
        "/api/watches", headers=headers, json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048}
    )
    assert r.status_code == 403


def test_create_watch_is_always_auto_book(client, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    _occupy(db_session, gpu, start, end)
    r = client.post(
        "/api/watches", headers=headers, json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048}
    )
    assert r.status_code == 201, r.text
    assert r.json()["auto_book"] is True


def test_create_watch_rejects_window_with_enough_free_ram(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    r = client.post(
        "/api/watches", headers=headers, json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048}
    )
    assert r.status_code == 422, r.text
    assert "already has enough free RAM" in r.json()["detail"]


def test_list_and_cancel_watch(client, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    _occupy(db_session, gpu, start, end)
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
