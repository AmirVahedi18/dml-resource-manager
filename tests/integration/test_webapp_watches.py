from datetime import datetime

from dml_bot.db.models.gpu import GPU
from dml_bot.db.session import session_scope
from dml_bot.services import user_service, watch_service
from tests.integration.conftest import auth_headers


def test_watch_full_create_and_cancel_flow(api_client, lab_setup):
    headers = auth_headers(lab_setup["telegram_id"])
    server_id, gpu_id = lab_setup["server_id"], lab_setup["gpu_id"]

    servers_resp = api_client.get("/api/watches/new", headers=headers)
    assert servers_resp.status_code == 200
    assert "lab-server-1" in servers_resp.text

    gpus_resp = api_client.get(f"/api/watches/new/{server_id}", headers=headers)
    assert gpus_resp.status_code == 200
    assert "A100" in gpus_resp.text

    range_resp = api_client.get(f"/api/watches/new/{server_id}/{gpu_id}", headers=headers)
    assert range_resp.status_code == 200
    assert "next 7 days" in range_resp.text

    form_resp = api_client.get(f"/api/watches/new/{server_id}/{gpu_id}/week", headers=headers)
    assert form_resp.status_code == 200
    assert "min_ram_needed_mb" in form_resp.text

    create_resp = api_client.post(
        f"/api/watches/new/{server_id}/{gpu_id}/week", headers=headers, data={"min_ram_needed_mb": 2048}
    )
    assert create_resp.status_code == 200
    assert "Watch created" in create_resp.text

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        watches = watch_service.list_watches_for_user(session, user.id)
    assert len(watches) == 1
    watch_id = watches[0].id

    list_resp = api_client.get("/api/watches", headers=headers)
    assert list_resp.status_code == 200
    assert "2048" in list_resp.text

    cancel_resp = api_client.post(f"/api/watches/{watch_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert "cancelled" in cancel_resp.text

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        assert watch_service.list_watches_for_user(session, user.id) == []


def test_cannot_cancel_another_users_watch(api_client, lab_setup):
    with session_scope() as session:
        gpu = session.get(GPU, lab_setup["gpu_id"])
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        watch = watch_service.create_watch(
            session, user, gpu, datetime(2026, 8, 1), datetime(2026, 8, 2), 1000
        )
        watch_id = watch.id
        user_service.register_user(session, telegram_id=777, full_name="Mallory")

    response = api_client.post(f"/api/watches/{watch_id}/cancel", headers=auth_headers(777))
    assert response.status_code == 404
