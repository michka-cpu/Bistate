from fastapi.testclient import TestClient


def test_import_runs_enrichment_and_underwriting_pipeline(client: TestClient) -> None:
    response = client.post(
        "/api/properties/import",
        json={
            "listing_url": "https://www.zillow.com/homedetails/12-Maple-St-Kingston-NY-12401/123_zpid/",
            "raw_address": "12 Maple St, Kingston, NY 12401",
            "mls_number": "MLS-123",
        },
    )

    assert response.status_code == 201
    prop = response.json()
    assert prop["listing_source"] == "Zillow"
    assert prop["address"] == "12 Maple St"
    assert prop["status"] == "Reviewing"
    assert prop["underwriting_output"]["traceability"]["workbook"].endswith("Underwriting_Model.xlsx")
    assert prop["overall_score"] is not None
    assert set(prop["enrichment_data"]) >= {
        "fema_flood", "school_ratings", "str_regulations", "airport_drive_time", "nyc_drive_time",
        "hospital_distance", "grocery_distance", "walkability", "wedding_suitability",
        "airbnb_suitability", "zoning", "parcel_information",
    }
    for field in prop["enrichment_data"].values():
        assert set(field) == {"value", "source", "last_updated", "confidence", "missing_reason"}


def test_import_requires_an_identifier(client: TestClient) -> None:
    assert client.post("/api/properties/import", json={}).status_code == 422


def test_refresh_enrichment_underwriting_and_report(client: TestClient) -> None:
    prop = client.post("/api/properties/import", json={"raw_address": "8 River Rd, Hudson, NY 12534"}).json()
    property_id = prop["id"]
    update = client.put(
        f"/api/properties/{property_id}",
        json={"asking_price": 725000, "annual_taxes": 14000, "bedrooms": 5, "acreage": 12, "status": "Needs Info"},
    )
    assert update.status_code == 200
    assert update.json()["status"] == "Needs Info"

    enriched = client.post(f"/api/properties/{property_id}/enrich")
    assert enriched.status_code == 200
    assert enriched.json()["enrichment_data"]["wedding_suitability"]["value"] > 50

    underwritten = client.post(f"/api/properties/{property_id}/underwrite")
    assert underwritten.status_code == 200
    assert underwritten.json()["assumptions"]["purchase_price"] == 725000
    assert underwritten.json()["assumptions"]["property_tax"] == 14000

    memo = client.get(f"/api/properties/{property_id}/report")
    assert memo.status_code == 200
    body = memo.json()
    assert body["property_id"] == property_id
    assert body["cash_required"] > 0
    assert "underwriting_explanation" in body
    assert "comparable_properties" in body
    assert body["confidence_score"] > 0
