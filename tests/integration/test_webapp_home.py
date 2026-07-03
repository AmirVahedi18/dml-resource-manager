from tests.integration.conftest import ADMIN_TELEGRAM_ID, auth_headers


def test_shell_page_loads_without_auth(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    assert "telegram-web-app.js" in response.text
    assert 'hx-get="/api/home"' in response.text


def test_home_requires_init_data(api_client):
    response = api_client.get("/api/home")
    assert response.status_code == 401


def test_home_rejects_tampered_init_data(api_client):
    headers = auth_headers(555)
    headers["X-Telegram-Init-Data"] = headers["X-Telegram-Init-Data"].replace("Test", "Evil")
    response = api_client.get("/api/home", headers=headers)
    assert response.status_code == 401


def test_home_shows_student_menu_for_registered_user(api_client, lab_setup):
    response = api_client.get("/api/home", headers=auth_headers(lab_setup["telegram_id"]))
    assert response.status_code == 200
    assert "Alice" in response.text
    assert "Reserve GPU" in response.text
    assert "Admin" not in response.text


def test_home_shows_admin_panel_for_admin(api_client):
    response = api_client.get("/api/home", headers=auth_headers(ADMIN_TELEGRAM_ID))
    assert response.status_code == 200
    assert "Admin" in response.text
    assert "Manage Users" in response.text


def test_home_shows_unregistered_message_for_unknown_user(api_client):
    response = api_client.get("/api/home", headers=auth_headers(123456789))
    assert response.status_code == 200
    assert "not registered" in response.text
    assert "123456789" in response.text
