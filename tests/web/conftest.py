import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from dml_bot.config.schema import AppConfig, RegulationConfig
from dml_bot.db.session import dispose_engine, init_engine
from dml_bot.services import auth_service, regulation_service, server_access_service, server_service
from dml_web import security
from dml_web.main import create_app


@pytest.fixture()
def db_session():
    engine = init_engine(":memory:")
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    regulation_service.ensure_seeded(session, RegulationConfig())
    session.commit()
    yield session
    session.close()
    dispose_engine()


@pytest.fixture()
def client(db_session):
    security.configure(secret="test-secret", expire_minutes=60)
    app = create_app(AppConfig())
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_user(db_session):
    user = auth_service.create_user_with_credentials(db_session, "admin1", "adminpass123", "Admin One")
    from dml_bot.services import user_service

    user_service.set_admin(db_session, user, True)
    db_session.commit()
    return user


@pytest.fixture()
def admin_headers(client, admin_user):
    return login(client, "admin1", "adminpass123")


@pytest.fixture()
def student_user(db_session):
    user = auth_service.create_user_with_credentials(db_session, "stud1", "studpass123", "Student One")
    db_session.commit()
    return user


@pytest.fixture()
def student_headers(client, student_user):
    return login(client, "stud1", "studpass123")


@pytest.fixture()
def server_and_gpu(db_session):
    server = server_service.create_server(db_session, "srv-1")
    gpu = server_service.add_gpu(db_session, server, 0, "A100", 40960)
    db_session.commit()
    return server, gpu


@pytest.fixture()
def student_with_access(db_session, student_user, server_and_gpu):
    server, _ = server_and_gpu
    server_access_service.set_access(db_session, student_user.id, {server.id})
    db_session.commit()
    return student_user
