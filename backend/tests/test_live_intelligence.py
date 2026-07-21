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
    assert data["fema_flood"]["source"] == "FEMA National Flood Hazard Layer"


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


def test_fema_provider_parses_official_nfhl_response(monkeypatch) -> None:
    from app.services import enrichment
    prop = Property(name="Test", address="1 Test St", city="Hudson", state="NY", latitude=42.25, longitude=-73.8)
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_args, **_kwargs: {"features": [{"attributes": {"FLD_ZONE": "AE", "SFHA_TF": "T", "FLD_ZONE_SUBTY": "FLOODWAY"}}]})
    field = enrichment.FemaFloodProvider().fetch(prop)
    assert field["value"]["flood_zone"] == "AE"
    assert field["value"]["flood_risk"] == "special_flood_hazard_area"


def test_census_geocoder_persists_coordinates(monkeypatch) -> None:
    from app.services import enrichment
    prop = Property(name="Test", address="1 Test St", city="Hudson", state="NY")
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_args, **_kwargs: {"result": {"addressMatches": [{"coordinates": {"x": -73.8, "y": 42.25}, "addressComponents": {"zip": "12534"}}]}})
    field = enrichment.CensusGeocoder().fetch(prop)
    assert field["value"]["latitude"] == 42.25
    assert (prop.latitude, prop.longitude) == (42.25, -73.8)
