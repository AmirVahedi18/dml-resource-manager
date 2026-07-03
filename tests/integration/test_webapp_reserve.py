from datetime import date, timedelta

from dml_bot.db.session import session_scope
from dml_bot.services import reservation_service, user_service
from tests.integration.conftest import auth_headers


def test_reserve_grid_and_create_flow(api_client, lab_setup):
    headers = auth_headers(lab_setup["telegram_id"])
    server_id, gpu_id = lab_setup["server_id"], lab_setup["gpu_id"]

    servers_resp = api_client.get("/api/reserve", headers=headers)
    assert servers_resp.status_code == 200
    assert "lab-server-1" in servers_resp.text

    gpus_resp = api_client.get(f"/api/reserve/{server_id}", headers=headers)
    assert gpus_resp.status_code == 200
    assert "A100" in gpus_resp.text

    dates_resp = api_client.get(f"/api/reserve/{server_id}/{gpu_id}", headers=headers)
    assert dates_resp.status_code == 200

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    grid_resp = api_client.get(f"/api/reserve/{server_id}/{gpu_id}/{tomorrow}", headers=headers)
    assert grid_resp.status_code == 200
    assert "grid-picker-container" in grid_resp.text
    assert 'data-readonly="true"' not in grid_resp.text  # reserve grid must stay interactive

    start = f"{tomorrow}T08:00:00"
    end = f"{tomorrow}T10:00:00"
    create_resp = api_client.post(
        f"/api/reserve/{server_id}/{gpu_id}",
        headers=headers,
        data={"start": start, "end": end, "ram_mb": 4096},
    )
    assert create_resp.status_code == 200
    assert "confirmed" in create_resp.text

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        reservations = reservation_service.list_active_reservations_for_user(session, user.id)
    assert len(reservations) == 1
    assert reservations[0].ram_mb == 4096


def test_reserve_create_rejects_invalid_request(api_client, lab_setup):
    headers = auth_headers(lab_setup["telegram_id"])
    server_id, gpu_id = lab_setup["server_id"], lab_setup["gpu_id"]

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = api_client.post(
        f"/api/reserve/{server_id}/{gpu_id}",
        headers=headers,
        data={"start": f"{tomorrow}T08:05:00", "end": f"{tomorrow}T10:00:00", "ram_mb": 4096},
    )
    assert response.status_code == 200
    assert "Could not create reservation" in response.text
    assert "align" in response.text


def test_reserve_requires_registration(api_client):
    response = api_client.get("/api/reserve", headers=auth_headers(123456789))
    assert response.status_code == 403
