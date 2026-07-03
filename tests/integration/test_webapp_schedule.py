from datetime import timedelta

from dml_bot.db.models.gpu import GPU
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, user_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.conftest import auth_headers


def test_schedule_requires_registration(api_client):
    response = api_client.get("/api/schedule", headers=auth_headers(123456789))
    assert response.status_code == 403


def test_schedule_server_and_gpu_listing(api_client, lab_setup):
    headers = auth_headers(lab_setup["telegram_id"])

    servers_resp = api_client.get("/api/schedule", headers=headers)
    assert servers_resp.status_code == 200
    assert "lab-server-1" in servers_resp.text

    gpus_resp = api_client.get(f"/api/schedule/{lab_setup['server_id']}", headers=headers)
    assert gpus_resp.status_code == 200
    assert "A100" in gpus_resp.text


def test_schedule_grid_reflects_existing_reservation(api_client, lab_setup):
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=2)
    end = start + timedelta(hours=1)
    with session_scope() as session:
        gpu = session.get(GPU, lab_setup["gpu_id"])
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation)

    headers = auth_headers(lab_setup["telegram_id"])
    day = start.date().isoformat()
    response = api_client.get(f"/api/schedule/{lab_setup['server_id']}/{lab_setup['gpu_id']}/{day}", headers=headers)

    assert response.status_code == 200
    assert '"free_mb": 36864' in response.text or "36864" in response.text
    assert 'data-readonly="true"' in response.text
