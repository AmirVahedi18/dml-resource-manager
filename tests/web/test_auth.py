from tests.web.conftest import login


def test_login_success(client, student_user):
    r = client.post("/api/auth/login", json={"username": "stud1", "password": "studpass123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password(client, student_user):
    r = client.post("/api/auth/login", json={"username": "stud1", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_username(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_returns_current_user(client, student_user):
    headers = login(client, "stud1", "studpass123")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "stud1"
    assert body["full_name"] == "Student One"
    assert body["is_admin"] is False


def test_change_password_requires_correct_old_password(client, student_user):
    headers = login(client, "stud1", "studpass123")
    r = client.post(
        "/api/auth/change-password", headers=headers, json={"old_password": "wrong", "new_password": "newpass123"}
    )
    assert r.status_code == 401

    r = client.post("/api/auth/login", json={"username": "stud1", "password": "studpass123"})
    assert r.status_code == 200


def test_change_password_success(client, student_user):
    headers = login(client, "stud1", "studpass123")
    r = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": "studpass123", "new_password": "newpass123"},
    )
    assert r.status_code == 204

    assert client.post("/api/auth/login", json={"username": "stud1", "password": "studpass123"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "stud1", "password": "newpass123"}).status_code == 200
