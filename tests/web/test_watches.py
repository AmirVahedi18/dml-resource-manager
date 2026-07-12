from datetime import datetime, timedelta, timezone

from tests.factories import make_user
from tests.web.conftest import login


def _future_range(hours_from_now=1, span_hours=10):
    start = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).replace(
        minute=0, second=0, microsecond=0
    )
    end = start + timedelta(hours=span_hours)
    return start.isoformat(), end.isoformat()


def _occupy(db_session, gpu, start, end):
    """Books enough of `gpu`, overlapping a single aligned slot at `start`, that it has no free
    RAM left there -- so `min_free_ram_in_range` reports 0 somewhere inside [start, end) and a
    watch can be created for that window (watch creation is rejected when the GPU already has
    enough free RAM). Splits across multiple occupiers since a single reservation is capped at
    the regulation's max_ram_per_reservation_gb, which can be well under the GPU's total RAM."""
    from dml_core.services import regulation_service, reservation_service

    regulation = regulation_service.get_regulation(db_session)
    slot = timedelta(minutes=regulation.min_reservation_slot_minutes)
    occupied_start = datetime.fromisoformat(start)
    occupied_end = occupied_start + slot

    reservations = []
    remaining = gpu.total_ram_mb
    while remaining > 0:
        chunk = min(remaining, regulation.max_ram_per_reservation_gb * 1024)
        occupier = make_user(db_session)
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
        "/api/watches", headers=headers,
        json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048, "description": "training run"},
    )
    assert r.status_code == 403


def test_create_watch_is_always_auto_book(client, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    _occupy(db_session, gpu, start, end)
    r = client.post(
        "/api/watches", headers=headers,
        json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048, "description": "training run"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["auto_book"] is True
    assert "description" not in r.json()


def test_create_watch_description_is_mandatory(client, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    _occupy(db_session, gpu, start, end)
    r = client.post(
        "/api/watches", headers=headers,
        json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048},
    )
    assert r.status_code == 422


def test_create_watch_rejects_window_with_enough_free_ram(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    r = client.post(
        "/api/watches", headers=headers,
        json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048, "description": "training run"},
    )
    assert r.status_code == 422, r.text
    assert "already has enough free RAM" in r.json()["detail"]


def test_create_watch_rejects_duration_exceeding_regulation_max(client, db_session, student_with_access, server_and_gpu):
    from dml_core.services import regulation_service

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    start, end = _future_range(span_hours=regulation.max_duration_hours + 1)
    r = client.post(
        "/api/watches", headers=login(client, "stud1", "studpass123"),
        json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048, "description": "training run"},
    )
    assert r.status_code == 422


def test_create_watch_rejects_ram_exceeding_regulation_cap(client, db_session, student_with_access, server_and_gpu):
    from dml_core.services import regulation_service

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    start, end = _future_range()
    over_cap_mb = regulation.max_ram_per_reservation_gb * 1024 + 1
    r = client.post(
        "/api/watches", headers=login(client, "stud1", "studpass123"),
        json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": over_cap_mb, "description": "training run"},
    )
    assert r.status_code == 422


def test_create_watch_rejects_non_positive_ram(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    start, end = _future_range()
    headers = login(client, "stud1", "studpass123")
    for bad_ram in (0, -1024):
        r = client.post(
            "/api/watches", headers=headers,
            json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": bad_ram, "description": "training run"},
        )
        assert r.status_code == 422


def test_create_watch_rejects_overlapping_watch_for_same_user(client, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    _occupy(db_session, gpu, start, end)
    r = client.post(
        "/api/watches", headers=headers,
        json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048, "description": "first watch"},
    )
    assert r.status_code == 201, r.text

    # Same exact window as the first watch -- guarantees it still lacks enough free RAM (so the
    # router's free-RAM precheck doesn't short-circuit before the overlap check runs) while also
    # unambiguously overlapping the first watch.
    r = client.post(
        "/api/watches", headers=headers,
        json={
            "gpu_id": gpu.id, "range_start": start, "range_end": end,
            "min_ram_needed_mb": 2048, "description": "overlapping watch",
        },
    )
    assert r.status_code == 422
    assert "overlapping" in r.json()["detail"]


def test_list_and_cancel_watch(client, db_session, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")
    start, end = _future_range()
    _occupy(db_session, gpu, start, end)
    watch = client.post(
        "/api/watches", headers=headers,
        json={"gpu_id": gpu.id, "range_start": start, "range_end": end, "min_ram_needed_mb": 2048, "description": "training run"},
    ).json()

    r = client.get("/api/watches", headers=headers)
    assert len(r.json()) == 1

    r = client.delete(f"/api/watches/{watch['id']}", headers=headers)
    assert r.status_code == 204
    assert client.get("/api/watches", headers=headers).json() == []


def test_scheduler_autobooks_matching_watch(db_session, student_with_access, server_and_gpu):
    from dml_core.services import regulation_service, watch_service
    from dml_web.scheduler import run_watch_autobook_check

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=5)
    watch = watch_service.create_watch(db_session, student_with_access, gpu, start, end, 4096, regulation, auto_book=True)
    db_session.commit()

    booked = run_watch_autobook_check(db_session)
    db_session.commit()

    assert booked == 1
    remaining = watch_service.list_watches_for_user(db_session, student_with_access.id, active_only=True)
    assert remaining == []


def test_watch_description_carries_into_autobooked_reservation(client, db_session, student_with_access, server_and_gpu):
    from dml_core.services import regulation_service, reservation_service, watch_service
    from dml_web.scheduler import run_watch_autobook_check

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=5)
    watch_service.create_watch(
        db_session, student_with_access, gpu, start, end, 4096, regulation, auto_book=True, description="Thesis experiments"
    )
    db_session.commit()

    booked = run_watch_autobook_check(db_session)
    db_session.commit()
    assert booked == 1

    [reservation] = reservation_service.list_active_reservations_for_user(db_session, student_with_access.id)
    assert reservation.description == "Thesis experiments"
