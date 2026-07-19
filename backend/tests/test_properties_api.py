from fastapi.testclient import TestClient

PAYLOAD = {
    "name": "Maple House",
    "address": "12 Maple Street",
    "city": "Kingston",
    "state": "NY",
    "postal_code": "12401",
    "notes": "Walkable location",
}


def test_create_list_and_get_property(client: TestClient) -> None:
    created = client.post("/api/properties", json=PAYLOAD)

    assert created.status_code == 201
    property_id = created.json()["id"]
    assert created.json()["name"] == "Maple House"

    listed = client.get("/api/properties")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [property_id]

    fetched = client.get(f"/api/properties/{property_id}")
    assert fetched.status_code == 200
    assert fetched.json()["address"] == PAYLOAD["address"]


def test_update_and_delete_property(client: TestClient) -> None:
    property_id = client.post("/api/properties", json=PAYLOAD).json()["id"]

    updated = client.put(f"/api/properties/{property_id}", json={"name": "Updated Maple House"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Maple House"

    deleted = client.delete(f"/api/properties/{property_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/properties/{property_id}").status_code == 404
