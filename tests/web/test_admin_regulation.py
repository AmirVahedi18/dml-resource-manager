def test_get_and_update_regulation(client, admin_headers):
    r = client.get("/api/admin/regulation", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()

    body["max_duration_hours"] = 6
    r = client.put("/api/admin/regulation", headers=admin_headers, json=body)
    assert r.status_code == 200
    assert r.json()["max_duration_hours"] == 6

    r = client.get("/api/regulation", headers=admin_headers)
    assert r.json()["max_duration_hours"] == 6
