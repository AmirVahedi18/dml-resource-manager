import pytest

from dml_bot.config.schema import AppConfig
from dml_bot.db.session import dispose_engine, init_engine, session_scope
from dml_bot.services import regulation_service, server_access_service, server_service, user_service


@pytest.fixture()
def lab_setup():
    """Boots a fresh in-memory DB with one server/GPU/regulation/student, used by most flow tests."""
    init_engine(":memory:")
    with session_scope() as session:
        server = server_service.create_server(session, "lab-server-1")
        gpu = server_service.add_gpu(session, server, 0, "A100", 40960)
        regulation_service.ensure_seeded(session, AppConfig().regulation)
        user = user_service.register_user(session, telegram_id=555, full_name="Alice")
        server_access_service.set_access(session, user.id, {server.id})
        ids = {"server_id": server.id, "gpu_id": gpu.id, "telegram_id": user.telegram_id}
    yield ids
    dispose_engine()
