from datetime import datetime, timedelta, timezone


def test_ranked_usage_by_user_and_by_gpu(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_bot.services import reservation_service, regulation_service

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=2)
    reservation_service.create_reservation(db_session, student_with_access, gpu, start, end, 4096, regulation)
    db_session.commit()

    range_start = start - timedelta(hours=1)
    range_end = end + timedelta(hours=1)

    r = client.get(
        "/api/admin/usage/ranked", headers=admin_headers,
        params={"range_start": range_start.isoformat(), "range_end": range_end.isoformat(), "metric": "gpu_hours"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["labels"] == ["Student One"]
    assert body["values"][0] == 2.0

    r = client.get(
        "/api/admin/usage/ranked", headers=admin_headers,
        params={"range_start": range_start.isoformat(), "range_end": range_end.isoformat(), "metric": "ram_gb_hours"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["labels"]) == 1
    assert body["values"][0] == 8.0  # 4GB * 2h


def test_historical_availability(client, admin_headers, db_session, student_with_access, server_and_gpu):
    from dml_bot.services import reservation_service, regulation_service

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=2)
    reservation_service.create_reservation(db_session, student_with_access, gpu, start, end, 4096, regulation)
    db_session.commit()

    r = client.get(
        "/api/admin/usage/historical-availability", headers=admin_headers,
        params={"gpu_id": gpu.id, "start_date": start.date().isoformat(), "days": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["capacity_mb"] == gpu.total_ram_mb
    assert len(body["segments"]) == 1
