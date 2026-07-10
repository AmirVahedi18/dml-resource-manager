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


def test_cannot_revoke_last_remaining_admin(client, admin_headers, admin_user):
    r = client.patch(f"/api/admin/users/{admin_user.id}/admin", headers=admin_headers, json={"is_admin": False})
    assert r.status_code == 422


def test_can_revoke_admin_when_another_admin_exists(client, admin_headers, admin_user, student_user):
    client.patch(f"/api/admin/users/{student_user.id}/admin", headers=admin_headers, json={"is_admin": True})
    r = client.patch(f"/api/admin/users/{admin_user.id}/admin", headers=admin_headers, json={"is_admin": False})
    assert r.status_code == 200


def test_reset_password(client, admin_headers, student_user):
    r = client.post(f"/api/admin/users/{student_user.id}/reset-password", headers=admin_headers, json={"new_password": "brandnew123"})
    assert r.status_code == 204
    assert client.post("/api/auth/login", json={"username": "stud1", "password": "brandnew123"}).status_code == 200


def test_delete_user(client, admin_headers, student_user):
    r = client.delete(f"/api/admin/users/{student_user.id}", headers=admin_headers)
    assert r.status_code == 204
    usernames = [u["username"] for u in client.get("/api/admin/users", headers=admin_headers).json()]
    assert "stud1" not in usernames


def test_set_server_access(client, admin_headers, student_user, server_and_gpu):
    server, _ = server_and_gpu
    r = client.patch(
        f"/api/admin/users/{student_user.id}/server-access", headers=admin_headers, json={"server_ids": [server.id]}
    )
    assert r.status_code == 200
    assert r.json()["server_ids"] == [server.id]
