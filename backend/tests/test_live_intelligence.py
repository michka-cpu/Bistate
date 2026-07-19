from datetime import datetime, timedelta, timezone

from app.models.property import Property
from app.schemas.acquisition import PropertyImport
from app.services.enrichment import enrich_property, is_stale, provider_health
from app.services.listing_providers import normalize_listing


def test_supported_listing_provider_selection() -> None:
    assert normalize_listing(PropertyImport(listing_url="https://www.redfin.com/NY/Hudson/1-Test-St")).listing_source == "Redfin"
    assert normalize_listing(PropertyImport(listing_url="https://example.test/listing")).listing_source == "manual"


def test_unconfigured_enrichment_has_provenance_and_explicit_missing_reason() -> None:
    data, errors = enrich_property(Property(name="Test", address="1 Test St", city="Hudson", state="NY"))
    assert not errors
    assert data["fema_flood"]["value"] is None
    assert data["fema_flood"]["missing_reason"]
    assert set(data["fema_flood"]) == {"value", "source", "confidence", "last_updated", "missing_reason"}


def test_stale_data_detection() -> None:
    assert is_stale({"last_updated": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()})
    assert not is_stale({"last_updated": datetime.now(timezone.utc).isoformat()})


def test_provider_health_is_explicit() -> None:
    assert all(item["status"] in {"configured", "unavailable"} for item in provider_health())


def test_refresh_keeps_the_complete_enrichment_contract(client) -> None:
    imported = client.post("/api/properties/import", json={"raw_address": "1 Test St, Hudson, NY 12534"})
    initial = imported.json()["enrichment_data"]
    refreshed = client.post(f"/api/properties/{imported.json()['id']}/enrich")
    assert refreshed.status_code == 200
    assert set(refreshed.json()["enrichment_data"]) == set(initial)
