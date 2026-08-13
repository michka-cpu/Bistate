from datetime import datetime, timedelta, timezone

from app.models.property import Property
from app.schemas.acquisition import PropertyImport
from app.services.enrichment import enrich_property, is_stale, provider_health
from app.services.listing_providers import normalize_listing


def test_supported_listing_provider_selection() -> None:
    assert normalize_listing(PropertyImport(listing_url="https://www.redfin.com/NY/Hudson/1-Test-St")).listing_source == "Redfin"
    assert normalize_listing(PropertyImport(listing_url="https://example.test/listing")).listing_source == "manual"


def test_is_stale_treats_naive_timestamps_as_utc() -> None:
    reference = datetime(2026, 2, 5, tzinfo=timezone.utc)
    # A tz-naive persisted timestamp (as SQLite returns) must not raise when compared
    # to a tz-aware reference; it is interpreted as UTC.
    assert is_stale({"last_updated": "2026-01-01T00:00:00"}, reference) is True   # 35 days old
    assert is_stale({"last_updated": "2026-01-20T00:00:00"}, reference) is False  # 16 days old
    assert is_stale({"last_updated": "2026-01-20T00:00:00+00:00"}, reference) is False
    assert is_stale({"last_updated": None}, reference) is True
    assert is_stale({"last_updated": "not-a-date"}, reference) is True


def test_unconfigured_enrichment_has_provenance_and_explicit_missing_reason() -> None:
    data, errors = enrich_property(Property(name="Test", address="1 Test St", city="Hudson", state="NY"))
    assert not errors
    assert data["fema_flood"]["value"] is None
    assert data["fema_flood"]["missing_reason"]
    assert set(data["fema_flood"]) == {"value", "source", "retrieval_status", "confidence", "last_updated", "missing_reason"}
    assert data["fema_flood"]["source"] == "FEMA National Flood Hazard Layer"


def test_google_routing_and_places_are_persisted_with_provenance(monkeypatch) -> None:
    from app.services import enrichment

    settings = enrichment.get_settings()
    monkeypatch.setattr(settings, "live_providers_enabled", True)
    monkeypatch.setattr(settings, "routing_api_key", "routing-key")
    monkeypatch.setattr(settings, "places_api_key", "places-key")

    def response(url, params):
        if "hazards.fema.gov" in url:
            return {"features": []}  # keyless FEMA lookup: outside a special flood hazard area
        if "directions" in url:
            return {"status": "OK", "routes": [{"legs": [{"distance": {"value": 16093, "text": "10 mi"}, "duration": {"value": 1200, "text": "20 mins"}}]}]}
        return {"status": "OK", "results": [{"name": "Hudson Amtrak", "vicinity": "Hudson, NY", "place_id": "place-1", "geometry": {"location": {"lat": 42.25, "lng": -73.8}}}]}

    monkeypatch.setattr(enrichment.HTTP, "get", response)
    prop = Property(name="Ghent", address="139 County Route 21C", city="Ghent", state="NY", latitude=42.2, longitude=-73.6)
    data, errors = enrichment.enrich_property(prop)

    assert not errors
    assert data["nyc_drive_time"]["retrieval_status"] == "live"
    assert data["nyc_drive_time"]["value"]["distance_miles"] == 10.0
    for key in ("nearest_amtrak", "restaurant_hub", "nearest_airport", "hospital_distance", "grocery_distance"):
        assert data[key]["source"] == "Google Places API"
        assert data[key]["value"]["drive_time_minutes"] == 20


def test_provider_http_responses_are_cached(monkeypatch) -> None:
    from app.services import enrichment

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return b'{"value": "cached"}'

    calls = []
    monkeypatch.setattr(enrichment.get_settings(), "provider_cache_seconds", 60)
    monkeypatch.setattr(enrichment, "urlopen", lambda *_args, **_kwargs: calls.append(1) or Response())
    client = enrichment.JsonHttpClient()

    assert client.get("https://provider.example/data", {"q": "Ghent"}) == {"value": "cached"}
    assert client.get("https://provider.example/data", {"q": "Ghent"}) == {"value": "cached"}
    assert len(calls) == 1


def test_provider_failure_retains_existing_live_fact(monkeypatch) -> None:
    from app.services import enrichment
    prop = Property(name="Ghent", address="139 County Route 21C", city="Ghent", state="NY")
    prop.enrichment_data = {"fema_flood": {"value": {"flood_zone": "X"}, "source": "FEMA", "retrieval_status": "live", "confidence": 0.9, "last_updated": "2000-01-01T00:00:00+00:00", "missing_reason": None}}
    monkeypatch.setattr(enrichment.FemaFloodProvider, "fetch", lambda *_: (_ for _ in ()).throw(enrichment.ProviderError("temporary failure")))
    data, errors = enrichment.enrich_property(prop, refresh=True)
    assert data["fema_flood"]["value"] == {"flood_zone": "X"}
    assert errors["fema_flood"]["message"] == "temporary failure"


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


def test_census_geocoder_populates_locality_and_geography(monkeypatch) -> None:
    """One keyless geographies call resolves and persists coordinates, ZIP, and county,
    and stashes the tract for the demographics adapter to reuse."""
    from app.services import enrichment
    prop = Property(name="Ghent", address="139 County Route 21C", city="Ghent", state="NY")
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    response = {"result": {"addressMatches": [{
        "matchedAddress": "139 CO RD 21C, GHENT, NY, 12075",
        "coordinates": {"x": -73.6057, "y": 42.2612},
        "addressComponents": {"zip": "12075", "state": "NY"},
        "geographies": {
            "Counties": [{"NAME": "Columbia County"}],
            "County Subdivisions": [{"NAME": "Ghent town"}],
            "Census Tracts": [{"STATE": "36", "COUNTY": "021", "TRACT": "000700"}],
        },
    }]}}
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_args, **_kwargs: response)
    field = enrichment.CensusGeocoder().fetch(prop)
    assert field["retrieval_status"] == "live"
    assert (prop.latitude, prop.longitude) == (42.2612, -73.6057)
    assert prop.postal_code == "12075"
    assert prop.county == "Columbia"  # trailing "County" stripped, not invented
    assert field["value"]["census_tract"] == "000700"
    assert prop._census_geography == {"state": "36", "county": "021", "tract": "000700"}


def test_census_geocoder_does_not_overwrite_user_locality(monkeypatch) -> None:
    from app.services import enrichment
    prop = Property(name="X", address="1 A St", city="Hudson", state="NY", county="Existing", postal_code="99999")
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"result": {"addressMatches": [{"coordinates": {"x": -73.8, "y": 42.25}, "addressComponents": {"zip": "12534"}, "geographies": {"Counties": [{"NAME": "Columbia County"}], "Census Tracts": [{"STATE": "36", "COUNTY": "021", "TRACT": "000700"}]}}]}})
    enrichment.CensusGeocoder().fetch(prop)
    assert prop.county == "Existing" and prop.postal_code == "99999"


def test_fema_error_envelope_is_disclosed_not_faked(monkeypatch) -> None:
    """A rate-limited FEMA response (HTTP 200 with an error envelope) is reported as a
    retryable provider error, never as a fabricated flood determination."""
    from app.services import enrichment
    prop = Property(name="X", address="1 A St", city="Hudson", state="NY", latitude=42.26, longitude=-73.6)
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"error": {"code": 400, "message": "Failed to execute query."}})
    data, errors = enrichment.enrich_property(prop)
    assert data["fema_flood"]["value"] is None
    assert "FEMA" in data["fema_flood"]["missing_reason"]
    assert "fema_flood" in errors


def test_error_envelopes_are_not_cached(monkeypatch) -> None:
    from app.services import enrichment
    calls = []
    class Resp:
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return self.body
    def fake_urlopen(*_a, **_k):
        calls.append(1)
        return Resp(b'{"error": {"code": 400}}')
    monkeypatch.setattr(enrichment, "urlopen", fake_urlopen)
    client = enrichment.JsonHttpClient()
    client.get("https://svc.example/q", {"a": "1"})
    client.get("https://svc.example/q", {"a": "1"})
    assert len(calls) == 2  # error envelope was not cached, so both calls hit the network


def test_elevation_provider_returns_feet(monkeypatch) -> None:
    from app.services import enrichment
    prop = Property(name="X", address="1 A St", city="Hudson", state="NY", latitude=42.26, longitude=-73.6)
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"value": 740.48})
    field = enrichment.ElevationProvider().fetch(prop)
    assert field["retrieval_status"] == "live"
    assert field["value"]["elevation_feet"] == 740.5


def test_demographics_requires_a_free_census_key(monkeypatch) -> None:
    """Without census_api_key the ACS data API is genuinely unavailable — disclosed, not faked."""
    from app.services import enrichment
    prop = Property(name="X", address="1 A St", city="Hudson", state="NY", latitude=42.26, longitude=-73.6)
    settings = enrichment.get_settings()
    monkeypatch.setattr(settings, "live_providers_enabled", True)
    monkeypatch.setattr(settings, "census_api_key", None)
    field = enrichment.CensusDemographicsProvider().fetch(prop)
    assert field["value"] is None
    assert "Census API key" in field["missing_reason"]
