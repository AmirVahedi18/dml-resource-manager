def test_create_rename_deactivate_delete_server(client, admin_headers):
    r = client.post("/api/admin/servers", headers=admin_headers, json={"name": "srv-a", "description": "rack a"})
    assert r.status_code == 201
    server_id = r.json()["id"]

    r = client.patch(f"/api/admin/servers/{server_id}/rename", headers=admin_headers, json={"name": "srv-a-renamed"})
    assert r.status_code == 200 and r.json()["name"] == "srv-a-renamed"

    r = client.patch(f"/api/admin/servers/{server_id}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False

    r = client.delete(f"/api/admin/servers/{server_id}", headers=admin_headers)
    assert r.status_code == 204
    assert client.get("/api/admin/servers", headers=admin_headers).json() == []


def test_duplicate_server_name_returns_409(client, admin_headers):
    client.post("/api/admin/servers", headers=admin_headers, json={"name": "dup-srv"})
    r = client.post("/api/admin/servers", headers=admin_headers, json={"name": "dup-srv"})
    assert r.status_code == 409


def test_add_rename_deactivate_delete_gpu(client, admin_headers, server_and_gpu):
    server, _ = server_and_gpu
    r = client.post(
        f"/api/admin/servers/{server.id}/gpus", headers=admin_headers,
        json={"index_on_server": 1, "model_name": "A100", "total_ram_mb": 40960},
    )
    assert r.status_code == 201
    gpu_id = r.json()["id"]

    r = client.patch(f"/api/admin/gpus/{gpu_id}/rename", headers=admin_headers, json={"model_name": "H100"})
    assert r.status_code == 200 and r.json()["model_name"] == "H100"

    r = client.patch(f"/api/admin/gpus/{gpu_id}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False

    r = client.delete(f"/api/admin/gpus/{gpu_id}", headers=admin_headers)
    assert r.status_code == 204


def test_duplicate_gpu_index_returns_409(client, admin_headers, server_and_gpu):
    server, gpu = server_and_gpu
    r = client.post(
        f"/api/admin/servers/{server.id}/gpus", headers=admin_headers,
        json={"index_on_server": gpu.index_on_server, "model_name": "A100", "total_ram_mb": 40960},
    )
    assert r.status_code == 409
