from datetime import datetime, timedelta, timezone

from dml_core.db.models.reservation import Reservation, ReservationStatus
from tests.web.conftest import login


def test_overview_requires_auth(client):
    assert client.get("/api/overview").status_code == 401


def test_overview_lists_accessible_server_with_free_gpu(client, student_with_access, server_and_gpu):
    _, gpu = server_and_gpu
    headers = login(client, "stud1", "studpass123")

    r = client.get("/api/overview", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    server = body[0]
    assert len(server["gpus"]) == 1
    g = server["gpus"][0]
    assert g["id"] == gpu.id
    assert g["total_ram_mb"] == gpu.total_ram_mb
    assert g["used_ram_mb"] == 0
    assert g["free_ram_mb"] == gpu.total_ram_mb
    assert g["active_reservations"] == 0


def test_overview_reflects_currently_active_reservation(
    client, db_session, student_with_access, server_and_gpu
):
    server, gpu = server_and_gpu
    # A reservation straddling "now" should count against the GPU's free RAM. Insert it
    # directly so we don't fight create_reservation's "no bookings in the past" rule.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        Reservation(
            user_id=student_with_access.id,
            gpu_id=gpu.id,
            start_time=now - timedelta(minutes=30),
            end_time=now + timedelta(minutes=30),
            ram_mb=4096,
            status=ReservationStatus.ACTIVE,
        )
    )
    db_session.commit()

    headers = login(client, "stud1", "studpass123")
    r = client.get("/api/overview", headers=headers)
    assert r.status_code == 200, r.text
    g = r.json()[0]["gpus"][0]
    assert g["used_ram_mb"] == 4096
    assert g["free_ram_mb"] == gpu.total_ram_mb - 4096
    assert g["active_reservations"] == 1


def test_overview_hides_servers_without_access(client, student_user, server_and_gpu):
    # Student exists but has no server access granted -> sees nothing.
    headers = login(client, "stud1", "studpass123")
    r = client.get("/api/overview", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == []
