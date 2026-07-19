from fastapi.testclient import TestClient


def _property_id(client: TestClient) -> int:
    return client.post("/api/properties/import", json={"raw_address": "1 Main St, Beacon, NY 12508"}).json()["id"]


def test_document_upload_list_download_and_delete(client: TestClient) -> None:
    property_id = _property_id(client)
    uploaded = client.post(
        f"/api/properties/{property_id}/documents",
        data={"document_type": "inspection"},
        files={"file": ("inspection.pdf", b"%PDF-test", "application/pdf")},
    )
    assert uploaded.status_code == 201
    document = uploaded.json()
    assert document["filename"] == "inspection.pdf"

    listed = client.get(f"/api/properties/{property_id}/documents")
    assert [item["id"] for item in listed.json()] == [document["id"]]
    downloaded = client.get(f"/api/properties/{property_id}/documents/{document['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-test"
    assert client.delete(f"/api/properties/{property_id}/documents/{document['id']}").status_code == 204


def test_notes_crud(client: TestClient) -> None:
    property_id = _property_id(client)
    created = client.post(
        f"/api/properties/{property_id}/notes", json={"body": "Confirm septic capacity", "author": "Acquisitions"}
    )
    assert created.status_code == 201
    assert client.get(f"/api/properties/{property_id}/notes").json()[0]["body"] == "Confirm septic capacity"
    assert client.delete(f"/api/properties/{property_id}/notes/{created.json()['id']}").status_code == 204


def test_tasks_crud(client: TestClient) -> None:
    property_id = _property_id(client)
    created = client.post(
        f"/api/properties/{property_id}/tasks",
        json={"title": "Call broker", "assignee": "Alex", "due_date": "2026-08-01"},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    updated = client.patch(f"/api/properties/{property_id}/tasks/{task_id}", json={"completed": True})
    assert updated.status_code == 200
    assert updated.json()["completed"] is True
    assert client.get(f"/api/properties/{property_id}/tasks").json()[0]["title"] == "Call broker"
    assert client.delete(f"/api/properties/{property_id}/tasks/{task_id}").status_code == 204
