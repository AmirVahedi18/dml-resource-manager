from datetime import timedelta

from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.reservation import Reservation, ReservationStatus
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, server_service, user_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.conftest import ADMIN_TELEGRAM_ID, auth_headers


def test_non_admin_rejected_from_admin_routes(api_client, lab_setup):
    headers = auth_headers(lab_setup["telegram_id"])
    for path in [
        "/api/admin/users",
        "/api/admin/servers",
        "/api/admin/regulation",
        "/api/admin/usage",
        "/api/admin/reservations",
    ]:
        response = api_client.get(path, headers=headers)
        assert response.status_code == 403, path


def test_admin_add_user_flow(api_client, lab_setup):
    headers = auth_headers(ADMIN_TELEGRAM_ID)

    list_resp = api_client.get("/api/admin/users", headers=headers)
    assert list_resp.status_code == 200
    assert "Alice" in list_resp.text

    create_resp = api_client.post(
        "/api/admin/users/new", headers=headers, data={"telegram_id": 424242, "full_name": "Charlie"}
    )
    assert create_resp.status_code == 200
    assert "Charlie" in create_resp.text

    with session_scope() as session:
        new_user = user_service.get_user_by_telegram_id(session, 424242)
    assert new_user is not None


def test_admin_toggle_active_and_privilege(api_client, lab_setup):
    headers = auth_headers(ADMIN_TELEGRAM_ID)
    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        user_id = user.id

    resp = api_client.post(f"/api/admin/users/{user_id}/toggle-active", headers=headers)
    assert resp.status_code == 200
    assert "🚫" in resp.text

    resp = api_client.post(f"/api/admin/users/{user_id}/toggle-privilege", headers=headers)
    assert resp.status_code == 200
    assert "⭐" in resp.text


def test_admin_add_server_and_gpu_flow(api_client, lab_setup):
    headers = auth_headers(ADMIN_TELEGRAM_ID)

    create_server_resp = api_client.post(
        "/api/admin/servers/new", headers=headers, data={"name": "lab-server-2"}
    )
    assert create_server_resp.status_code == 200
    assert "lab-server-2" in create_server_resp.text

    with session_scope() as session:
        new_server = next(s for s in server_service.list_servers(session) if s.name == "lab-server-2")

    create_gpu_resp = api_client.post(
        f"/api/admin/servers/new-gpu/{new_server.id}",
        headers=headers,
        data={"index_on_server": 0, "model_name": "RTX 4090", "total_ram_mb": 24576},
    )
    assert create_gpu_resp.status_code == 200
    assert "RTX 4090" in create_gpu_resp.text

    with session_scope() as session:
        server = next(s for s in server_service.list_servers(session) if s.name == "lab-server-2")
        gpus = server_service.list_gpus(session, server)
    assert len(gpus) == 1


def test_admin_update_regulation(api_client, lab_setup):
    headers = auth_headers(ADMIN_TELEGRAM_ID)

    resp = api_client.post("/api/admin/regulation/max_duration_hours", headers=headers, data={"value": 24})
    assert resp.status_code == 200
    assert "24" in resp.text

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    assert regulation.max_duration_hours == 24
    assert regulation.updated_by == ADMIN_TELEGRAM_ID


def test_admin_regulation_rejects_unknown_field(api_client, lab_setup):
    headers = auth_headers(ADMIN_TELEGRAM_ID)
    resp = api_client.get("/api/admin/regulation/not_a_real_field", headers=headers)
    assert resp.status_code == 404


def test_admin_usage_chart_renders_png(api_client, lab_setup):
    start = floor_to_slot(utc_now(), 30) - timedelta(days=2)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        gpu = session.get(GPU, lab_setup["gpu_id"])
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation, now=start - timedelta(hours=1))

    headers = auth_headers(ADMIN_TELEGRAM_ID)
    chart_resp = api_client.get("/api/admin/usage/user/week", headers=headers)
    assert chart_resp.status_code == 200
    assert "init_data=" in chart_resp.text

    # extract the query-param initData embedded in the page and hit the PNG endpoint the way an
    # <img> tag would: no custom header at all, auth via query param only.
    import re

    match = re.search(r'chart\.png\?init_data=([^"]+)', chart_resp.text)
    assert match is not None
    png_resp = api_client.get(f"/api/admin/usage/user/week/chart.png?init_data={match.group(1)}")
    assert png_resp.status_code == 200
    assert png_resp.headers["content-type"] == "image/png"
    assert png_resp.content.startswith(b"\x89PNG")


def test_admin_reservations_lab_wide_override_cancel(api_client, lab_setup):
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=3)
    end = start + timedelta(hours=1)
    with session_scope() as session:
        gpu = session.get(GPU, lab_setup["gpu_id"])
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        reservation = reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation)
        reservation_id = reservation.id

    headers = auth_headers(ADMIN_TELEGRAM_ID)
    list_resp = api_client.get("/api/admin/reservations", headers=headers)
    assert list_resp.status_code == 200
    assert "Alice" in list_resp.text

    detail_resp = api_client.get(f"/api/admin/reservations/{reservation_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert "admin override" in detail_resp.text.lower() or "Cancel" in detail_resp.text

    cancel_resp = api_client.post(f"/api/admin/reservations/{reservation_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert "cancelled" in cancel_resp.text

    with session_scope() as session:
        reservation = session.get(Reservation, reservation_id)
    assert reservation.status == ReservationStatus.CANCELLED
