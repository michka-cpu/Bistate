from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.models.property import Property
from app.services.property_intelligence import build_property_intelligence


def property_with(**kwargs):
    return Property(name="Diligence House", address="1 Main St", city="Hudson", state="NY", **kwargs)


def test_intelligence_preserves_provenance_and_unavailable_fields():
    prop = property_with()
    prop.enrichment_data = {"zoning": {"value": None, "source": "County zoning provider", "retrieval_status": "unavailable", "confidence": 0, "last_updated": None, "missing_reason": "Provider credentials are not configured"}}
    result = build_property_intelligence(prop)
    zoning = next(field for section in result["sections"] for field in section["fields"] if field["key"] == "zoning")
    assert zoning["source"] == "County zoning provider"
    assert zoning["display_status"] == "Provider not configured"
    assert zoning["value"] is None


def test_red_flags_and_opportunities_use_only_supported_facts():
    prop = property_with(acreage=8, annual_taxes=20_000, asking_price=500_000)
    prop.enrichment_data = {
        "fema_flood": {"value": {"flood_zone": "AE", "flood_risk": "special_flood_hazard_area"}},
        "nyc_drive_time": {"value": {"drive_time_minutes": 120}},
        "nearest_amtrak": {"value": {"name": "Hudson Amtrak"}},
    }
    result = build_property_intelligence(prop)
    assert any(item["severity"] == "High" and "fema_flood" in item["source_fields"] for item in result["red_flags"])
    assert {item["title"] for item in result["opportunities"]} >= {"Strong NYC access", "Nearby train service", "Land-based diligence potential"}


def test_completeness_is_coverage_and_reports_stale_separately():
    prop = property_with(acreage=2)
    prop.enrichment_data = {"zoning": {"value": "Rural", "source": "County", "retrieval_status": "live", "confidence": .95, "last_updated": "2000-01-01T00:00:00+00:00", "missing_reason": None}}
    result = build_property_intelligence(prop)
    completeness = result["completeness"]
    assert 0 < completeness["percentage_complete"] < 100
    assert completeness["stale_fields"] == 1
    assert "never affects acquisition scores" in completeness["method"]


def test_intelligence_endpoint_and_refresh_contract(client):
    created = client.post("/api/properties", json={"name": "Test", "address": "1 Main", "city": "Hudson", "state": "NY"}).json()
    response = client.get(f"/api/properties/{created['id']}/intelligence")
    assert response.status_code == 200
    assert [section["name"] for section in response.json()["sections"]] == ["Access", "Land and environment", "Infrastructure", "Regulatory", "Financial and civic"]
    assert client.post(f"/api/properties/{created['id']}/enrich").status_code == 200


def test_intelligence_endpoint_succeeds_for_persisted_property_with_acreage(client: TestClient) -> None:
    # Regression: the synthesized `confirmed_acreage`/`current_taxes` facts stamp the
    # property's persisted `updated_at`, which SQLite returns tz-naive. Staleness checks
    # must not raise when comparing that against a tz-aware "now".
    created = client.post("/api/properties", json={"name": "Acre House", "address": "9 Farm Rd", "city": "Ghent", "state": "NY"}).json()
    assert client.put(f"/api/properties/{created['id']}", json={"acreage": 12, "annual_taxes": 8000}).status_code == 200
    response = client.get(f"/api/properties/{created['id']}/intelligence")
    assert response.status_code == 200
    acreage = next(field for section in response.json()["sections"] for field in section["fields"] if field["key"] == "confirmed_acreage")
    assert acreage["value"] == 12
