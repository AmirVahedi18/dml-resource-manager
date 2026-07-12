def test_create_feedback_requires_auth(client):
    r = client.post("/api/feedback", json={"category": "BUG", "message": "the reserve button is broken"})
    assert r.status_code == 401


def test_create_and_list_own_feedback(client, student_headers):
    r = client.post(
        "/api/feedback", headers=student_headers,
        json={"category": "BUG", "message": "the reserve button is broken"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["category"] == "BUG"
    assert body["message"] == "the reserve button is broken"

    r = client.get("/api/feedback", headers=student_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["message"] == "the reserve button is broken"


def test_create_feedback_rejects_blank_message(client, student_headers):
    r = client.post("/api/feedback", headers=student_headers, json={"category": "OTHER", "message": "   "})
    assert r.status_code == 422


def test_create_feedback_rejects_invalid_category(client, student_headers):
    r = client.post("/api/feedback", headers=student_headers, json={"category": "NOT_A_CATEGORY", "message": "hi"})
    assert r.status_code == 422


def test_feedback_not_visible_to_other_students(client, student_headers, db_session):
    from dml_core.services import auth_service

    other = auth_service.create_user_with_credentials(db_session, "other1", "otherpass123", "Other One")
    db_session.commit()
    other_headers_login = client.post(
        "/api/auth/login", json={"username": "other1", "password": "otherpass123"}
    ).json()
    other_headers = {"Authorization": f"Bearer {other_headers_login['access_token']}"}

    client.post(
        "/api/feedback", headers=student_headers, json={"category": "BUG", "message": "my own bug report"}
    )

    r = client.get("/api/feedback", headers=other_headers)
    assert r.json() == []


def test_non_admin_cannot_list_all_feedback(client, student_headers):
    r = client.get("/api/admin/feedback", headers=student_headers)
    assert r.status_code == 403


def test_admin_sees_all_feedback(client, admin_headers, student_headers):
    client.post(
        "/api/feedback", headers=student_headers, json={"category": "PROBLEM", "message": "can't cancel a reservation"}
    )

    r = client.get("/api/admin/feedback", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["user_full_name"] == "Student One"
    assert body["items"][0]["message"] == "can't cancel a reservation"
    assert body["items"][0]["category"] == "PROBLEM"


def test_admin_filters_feedback_by_user_and_category(client, admin_headers, db_session):
    from dml_core.services import auth_service

    stud_a = auth_service.create_user_with_credentials(db_session, "studA", "studApass123", "Student A")
    stud_b = auth_service.create_user_with_credentials(db_session, "studB", "studBpass123", "Student B")
    db_session.commit()
    headers_a = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'username': 'studA', 'password': 'studApass123'}).json()['access_token']}"}
    headers_b = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'username': 'studB', 'password': 'studBpass123'}).json()['access_token']}"}

    client.post("/api/feedback", headers=headers_a, json={"category": "BUG", "message": "bug from A"})
    client.post("/api/feedback", headers=headers_b, json={"category": "SUGGESTION", "message": "suggestion from B"})

    r = client.get("/api/admin/feedback", headers=admin_headers, params={"user_id": stud_a.id})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["message"] == "bug from A"

    r = client.get("/api/admin/feedback", headers=admin_headers, params={"category": "SUGGESTION"})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["message"] == "suggestion from B"


def test_admin_deletes_feedback(client, admin_headers, student_headers):
    created = client.post(
        "/api/feedback", headers=student_headers, json={"category": "BUG", "message": "will be deleted"}
    ).json()

    r = client.delete(f"/api/admin/feedback/{created['id']}", headers=admin_headers)
    assert r.status_code == 204
    assert client.get("/api/admin/feedback", headers=admin_headers).json()["total"] == 0


def test_admin_delete_nonexistent_feedback_returns_404(client, admin_headers):
    r = client.delete("/api/admin/feedback/999999", headers=admin_headers)
    assert r.status_code == 404


def test_deleting_user_hard_deletes_their_feedback(client, admin_headers, db_session, student_user, student_headers):
    from dml_core.db.models.feedback import Feedback

    client.post("/api/feedback", headers=student_headers, json={"category": "BUG", "message": "bug before deletion"})
    db_session.commit()

    user_id = student_user.id
    r = client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)
    assert r.status_code == 204

    db_session.expire_all()
    assert db_session.query(Feedback).filter_by(user_id=user_id).count() == 0
