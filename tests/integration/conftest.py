import pytest
from fastapi.testclient import TestClient

from dml_bot.api.app import build_api_app
from dml_bot.config.schema import AppConfig
from dml_bot.db.session import dispose_engine, init_engine, session_scope
from dml_bot.services import regulation_service, server_service, user_service
from tests.webapp_signing import sign_init_data

BOT_TOKEN = "123456:test-bot-token"
ADMIN_TELEGRAM_ID = 999


@pytest.fixture()
def lab_setup():
    """Boots a fresh in-memory DB with one server/GPU/regulation/student, used by most flow tests."""
    init_engine(":memory:")
    with session_scope() as session:
        server = server_service.create_server(session, "lab-server-1")
        gpu = server_service.add_gpu(session, server, 0, "A100", 40960)
        regulation_service.ensure_seeded(session, AppConfig().regulation)
        user = user_service.register_user(session, telegram_id=555, full_name="Alice")
        ids = {"server_id": server.id, "gpu_id": gpu.id, "telegram_id": user.telegram_id}
    yield ids
    dispose_engine()


@pytest.fixture()
def api_client(lab_setup):
    """FastAPI TestClient wired up with the same DB as `lab_setup` and a fixed admin ID."""
    app = build_api_app(AppConfig(), BOT_TOKEN, {ADMIN_TELEGRAM_ID})
    return TestClient(app)


def auth_headers(telegram_id: int, **user_fields) -> dict:
    user = {"id": telegram_id, "first_name": "Test", **user_fields}
    return {"X-Telegram-Init-Data": sign_init_data(BOT_TOKEN, user)}
