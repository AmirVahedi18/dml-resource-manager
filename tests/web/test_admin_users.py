def test_non_admin_cannot_access_admin_routes(client, student_headers):
    r = client.get("/api/admin/users", headers=student_headers)
    assert r.status_code == 403


def test_bulk_create_users(client, admin_headers, server_and_gpu):
    server, _ = server_and_gpu
    r = client.post(
        "/api/admin/users/bulk",
        headers=admin_headers,
        json={
            "users": [
                {"username": "alice", "password": "alicepass123", "full_name": "Alice A", "server_ids": [server.id]},
                {"username": "bob", "password": "bobpass1234", "full_name": "Bob B"},
            ]
        },
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert all(res["success"] for res in results)

    users = client.get("/api/admin/users", headers=admin_headers).json()
    alice = next(u for u in users if u["username"] == "alice")
    assert alice["server_ids"] == [server.id]


def test_bulk_create_partial_failure_does_not_lose_earlier_rows(client, admin_headers, admin_user):
    r = client.post(
        "/api/admin/users/bulk",
        headers=admin_headers,
        json={
            "users": [
                {"username": "newuser1", "password": "newpass1234", "full_name": "New User"},
                {"username": "admin1", "password": "whatever123", "full_name": "duplicate"},  # already exists
            ]
        },
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["success"] is True
    assert results[1]["success"] is False

    usernames = [u["username"] for u in client.get("/api/admin/users", headers=admin_headers).json()]
    assert "newuser1" in usernames


def test_rename_activate_and_max_gpus(client, admin_headers, student_user):
    uid = student_user.id
    r = client.patch(f"/api/admin/users/{uid}/rename", headers=admin_headers, json={"full_name": "Renamed"})
    assert r.status_code == 200 and r.json()["full_name"] == "Renamed"

    r = client.patch(f"/api/admin/users/{uid}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False

    r = client.patch(f"/api/admin/users/{uid}/max-concurrent-gpus", headers=admin_headers, json={"max_concurrent_gpus": 3})
    assert r.status_code == 200 and r.json()["max_concurrent_gpus"] == 3


def test_non_bootstrap_admin_cannot_grant_admin(client, admin_headers, student_user):
    r = client.patch(f"/api/admin/users/{student_user.id}/admin", headers=admin_headers, json={"is_admin": True})
    assert r.status_code == 403


def test_bootstrap_admin_can_grant_admin(client, bootstrap_admin_headers, student_user):
    r = client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": True})
    assert r.status_code == 200 and r.json()["is_admin"] is True


def test_non_bootstrap_admin_cannot_revoke_own_admin_rights(client, admin_headers, admin_user):
    r = client.patch(f"/api/admin/users/{admin_user.id}/admin", headers=admin_headers, json={"is_admin": False})
    assert r.status_code == 403


def test_non_bootstrap_admin_cannot_revoke_other_admins_rights(client, admin_headers, bootstrap_admin_headers, student_user):
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": True})
    r = client.patch(f"/api/admin/users/{student_user.id}/admin", headers=admin_headers, json={"is_admin": False})
    assert r.status_code == 403


def test_bootstrap_admin_can_revoke_other_admins_rights(client, bootstrap_admin_headers, student_user):
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": True})
    r = client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": False})
    assert r.status_code == 200 and r.json()["is_admin"] is False


def test_bootstrap_admin_can_revoke_deactivated_admins_rights_when_not_last_admin(
    client, bootstrap_admin_headers, student_user
):
    # student_user becomes a second (non-bootstrap) admin, then gets deactivated -- revoking their
    # admin role should still succeed since the bootstrap admin is still an active admin.
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": True})
    client.patch(f"/api/admin/users/{student_user.id}/active", headers=bootstrap_admin_headers, json={"is_active": False})
    r = client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": False})
    assert r.status_code == 200 and r.json()["is_admin"] is False


def test_non_bootstrap_admin_cannot_deactivate_own_account(client, admin_headers, admin_user):
    r = client.patch(f"/api/admin/users/{admin_user.id}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 403


def test_non_bootstrap_admin_cannot_deactivate_other_admin(client, admin_headers, bootstrap_admin_headers, student_user):
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": True})
    r = client.patch(f"/api/admin/users/{student_user.id}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 403


def test_bootstrap_admin_can_deactivate_other_admin(client, bootstrap_admin_headers, student_user):
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": True})
    r = client.patch(f"/api/admin/users/{student_user.id}/active", headers=bootstrap_admin_headers, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False


def test_non_bootstrap_admin_cannot_delete_own_account(client, admin_headers, admin_user):
    r = client.delete(f"/api/admin/users/{admin_user.id}", headers=admin_headers)
    assert r.status_code == 403


def test_non_bootstrap_admin_cannot_delete_other_admin(client, admin_headers, bootstrap_admin_headers, student_user):
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": True})
    r = client.delete(f"/api/admin/users/{student_user.id}", headers=admin_headers)
    assert r.status_code == 403


def test_bootstrap_admin_can_delete_other_admin(client, bootstrap_admin_headers, student_user):
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=bootstrap_admin_headers, json={"is_admin": True})
    r = client.delete(f"/api/admin/users/{student_user.id}", headers=bootstrap_admin_headers)
    assert r.status_code == 204


def test_reset_password(client, admin_headers, student_user):
    r = client.post(f"/api/admin/users/{student_user.id}/reset-password", headers=admin_headers, json={"new_password": "brandnew123"})
    assert r.status_code == 204
    assert client.post("/api/auth/login", json={"username": "stud1", "password": "brandnew123"}).status_code == 200


def test_delete_user(client, admin_headers, student_user):
    r = client.delete(f"/api/admin/users/{student_user.id}", headers=admin_headers)
    assert r.status_code == 204

    # Login is revoked...
    assert client.post("/api/auth/login", json={"username": "stud1", "password": "studpass123"}).status_code == 401

    # ...and the account no longer appears at all.
    users = client.get("/api/admin/users", headers=admin_headers).json()
    assert all(u["id"] != student_user.id for u in users)


def test_delete_user_hard_deletes_their_reservations(
    client, admin_headers, db_session, student_with_access, server_and_gpu
):
    from datetime import datetime, timedelta, timezone

    from dml_core.services import reservation_service, regulation_service

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=2)
    reservation = reservation_service.create_reservation(
        db_session, student_with_access, gpu, start, end, 4096, regulation
    )
    db_session.commit()
    reservation_id = reservation.id
    user_id = student_with_access.id

    r = client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)
    assert r.status_code == 204

    from dml_core.db.models.reservation import Reservation
    from dml_core.db.models.user import User

    db_session.expire_all()
    assert db_session.get(Reservation, reservation_id) is None
    assert db_session.get(User, user_id) is None


def test_bootstrap_admin_cannot_be_deactivated(client, admin_headers, admin_user, monkeypatch):
    monkeypatch.setenv("WEB_ADMIN_USERNAME", admin_user.username)
    r = client.patch(f"/api/admin/users/{admin_user.id}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 422


def test_bootstrap_admin_cannot_be_de_adminned(client, admin_headers, admin_user, student_user, monkeypatch):
    # Grant a second admin first so this isn't also blocked by the "last remaining admin" guard.
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=admin_headers, json={"is_admin": True})
    monkeypatch.setenv("WEB_ADMIN_USERNAME", admin_user.username)
    r = client.patch(f"/api/admin/users/{admin_user.id}/admin", headers=admin_headers, json={"is_admin": False})
    assert r.status_code == 422


def test_bootstrap_admin_cannot_be_deleted(client, admin_headers, admin_user, monkeypatch):
    monkeypatch.setenv("WEB_ADMIN_USERNAME", admin_user.username)
    r = client.delete(f"/api/admin/users/{admin_user.id}", headers=admin_headers)
    assert r.status_code == 422


def test_set_server_access(client, admin_headers, student_user, server_and_gpu):
    server, _ = server_and_gpu
    r = client.patch(
        f"/api/admin/users/{student_user.id}/server-access", headers=admin_headers, json={"server_ids": [server.id]}
    )
    assert r.status_code == 200
    assert r.json()["server_ids"] == [server.id]


def test_revoking_server_access_cancels_users_reservations_there(
    client, admin_headers, db_session, student_with_access, server_and_gpu
):
    from datetime import datetime, timedelta, timezone

    from dml_core.db.models.reservation import Reservation, ReservationStatus
    from dml_core.services import regulation_service, reservation_service

    _, gpu = server_and_gpu
    regulation = regulation_service.get_regulation(db_session)
    start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    end = start + timedelta(hours=2)
    reservation = reservation_service.create_reservation(
        db_session, student_with_access, gpu, start, end, 4096, regulation
    )
    db_session.commit()
    reservation_id = reservation.id
    user_id = student_with_access.id

    r = client.patch(f"/api/admin/users/{user_id}/server-access", headers=admin_headers, json={"server_ids": []})
    assert r.status_code == 200
    assert r.json()["server_ids"] == []

    db_session.expire_all()
    assert db_session.get(Reservation, reservation_id).status == ReservationStatus.CANCELLED
