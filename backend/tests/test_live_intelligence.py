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


def test_keyless_osm_access_facts_are_computed_from_coordinates() -> None:
    # One Overpass response + one OSRM table → nearest POI per category with drive times.
    from app.services import enrichment
    prop = Property(name="Ghent", address="139 County Route 21C", city="Ghent", state="NY", latitude=42.20, longitude=-73.60)
    overpass_elements = [
        {"lat": 42.21, "lon": -73.61, "tags": {"railway": "station", "name": "Hudson"}},
        {"lat": 42.30, "lon": -73.80, "tags": {"aeroway": "aerodrome", "name": "Athens Airport"}},
        {"lat": 42.201, "lon": -73.601, "tags": {"amenity": "hospital", "name": "Columbia Memorial"}},
        {"lat": 42.60, "lon": -73.40, "tags": {"landuse": "winter_sports", "name": "Catamount"}},
    ]

    def fake_table(lat, lon, destinations):
        n = len(destinations)
        return [600.0] * n, [16093.0] * n  # 10 minutes / 10 mi to each destination + NYC

    import app.services.enrichment as e
    e_orig_over, e_orig_table = e._overpass_around, e._osrm_table
    try:
        e._overpass_around = lambda lat, lon: overpass_elements
        e._osrm_table = fake_table
        access = e._compute_access(prop)
    finally:
        e._overpass_around, e._osrm_table = e_orig_over, e_orig_table

    assert access["nearest_amtrak"]["name"] == "Hudson"
    assert access["nearest_amtrak"]["drive_time_minutes"] == 10
    assert access["nearest_airport"]["name"] == "Athens Airport"
    assert access["airport_drive_time"]["drive_time_minutes"] == 10
    assert access["hospital_distance"]["name"] == "Columbia Memorial"
    assert access["ski_access"]["name"] == "Catamount"
    assert access["nyc_drive_time"]["drive_time_minutes"] == 10 and access["nyc_drive_time"]["straight_line_miles"] > 0


def test_osm_access_provider_is_keyless_and_needs_only_coordinates(monkeypatch) -> None:
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment, "_compute_access", lambda prop: {"hospital_distance": {"name": "General", "drive_time_minutes": 4, "straight_line_miles": 2.0}})
    prop = Property(name="x", address="1 A St", city="Hudson", state="NY", latitude=42.25, longitude=-73.79)
    field = enrichment.OsmAccessProvider("hospital_distance", "hospital").fetch(prop)
    assert field["retrieval_status"] == "live" and field["source"].startswith("OpenStreetMap")
    assert field["value"]["drive_time_minutes"] == 4
    # No coordinates -> unavailable, and never a fabricated result.
    field2 = enrichment.OsmAccessProvider("hospital_distance", "hospital").fetch(Property(name="x", address="1 A St", city="Hudson", state="NY"))
    assert field2["value"] is None and "Coordinates are required" in field2["missing_reason"]


def test_fema_retries_the_error_envelope_then_succeeds(monkeypatch) -> None:
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def flaky(url, params):
        calls["n"] += 1
        if calls["n"] < 3:
            return {"error": {"code": 400}}          # rate-limited twice
        return {"features": []}                        # then succeeds: outside SFHA

    monkeypatch.setattr(enrichment.HTTP, "get", flaky)
    prop = Property(name="x", address="1 A St", city="Hudson", state="NY", latitude=42.25, longitude=-73.79)
    field = enrichment.FemaFloodProvider().fetch(prop)
    assert calls["n"] == 3
    assert field["retrieval_status"] == "live"
    assert field["value"]["flood_risk"] == "outside_mapped_special_flood_hazard_area"


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


def test_census_geocoder_backfills_placeholder_locality(monkeypatch) -> None:
    """A street parsed without a locality (Unknown/NA) is completed from the authoritative
    Census match, so a geocodable address is never left flagged as incomplete."""
    from app.services import enrichment
    prop = Property(name="139 County Route 21C", address="139 County Route 21C", city="Unknown", state="NA")
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"result": {"addressMatches": [{
        "matchedAddress": "139 CO RD 21C, GHENT, NY, 12075",
        "coordinates": {"x": -73.6057, "y": 42.2612},
        "addressComponents": {"zip": "12075", "state": "NY", "city": "GHENT"},
        "geographies": {"Counties": [{"NAME": "Columbia County"}], "Census Tracts": [{"STATE": "36", "COUNTY": "021", "TRACT": "000700"}]},
    }]}})
    enrichment.CensusGeocoder().fetch(prop)
    assert prop.city == "Ghent" and prop.state == "NY" and prop.postal_code == "12075"


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
    monkeypatch.setattr(enrichment.time, "sleep", lambda *_: None)
    monkeypatch.setattr(enrichment, "_compute_access", lambda prop: {})  # keep OSM/OSRM hermetic
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


def _ulster_prop() -> Property:
    return Property(name="Z", address="1 Main St", city="New Paltz", state="NY", county="Ulster", latitude=41.7476, longitude=-74.0868)


def test_zoning_provider_returns_the_verified_district_for_a_covered_county(monkeypatch) -> None:
    """A covered Catskills county (Ulster) resolves a real zoning district from public GIS."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"features": [{"attributes": {"ZONE_CODE": "B-2", "ZONE_DESC": "Core Business", "ZONE_GENERAL": "Business", "MUNICIPALI": "VNEWPAL", "YEAR": "2016"}}]})
    field = enrichment.ZoningProvider().fetch(_ulster_prop())
    assert field["retrieval_status"] == "live"
    assert field["value"] == {"district": "B-2", "description": "Core Business", "category": "Business", "as_of": "2016"}
    assert "Ulster County" in field["source"]


def test_zoning_provider_is_honest_when_coordinates_are_unzoned(monkeypatch) -> None:
    """Inside a covered county but outside any mapped district (e.g. an unzoned city),
    the provider discloses that rather than inventing a district."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"features": []})
    field = enrichment.ZoningProvider().fetch(_ulster_prop())
    assert field["value"] is None
    assert "outside a mapped zoning district" in field["missing_reason"]
    assert field["source"] is not None


def test_zoning_provider_is_unavailable_outside_supported_markets(monkeypatch) -> None:
    """A county with no mapped public zoning layer yields an honest unavailable — no call."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    def _forbidden(*_a, **_k): raise AssertionError("no HTTP call for an unsupported county")
    monkeypatch.setattr(enrichment.HTTP, "get", _forbidden)
    prop = Property(name="Z", address="1 Rd", city="Albany", state="NY", county="Albany", latitude=42.6526, longitude=-73.7562)
    field = enrichment.ZoningProvider().fetch(prop)
    assert field["value"] is None
    assert "Albany County" in field["missing_reason"]


def test_zoning_covers_town_of_catskill_greene(monkeypatch) -> None:
    """Greene County: the Town/Village of Catskill resolve a real district from the verified
    consultant-hosted zoning layers."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"features": [{"attributes": {"Zone": "Rural Residential/Agriculture"}}]})
    prop = Property(name="Z", address="1 Rd", city="Catskill", state="NY", county="Greene", latitude=42.23, longitude=-73.90)
    field = enrichment.ZoningProvider().fetch(prop)
    assert field["retrieval_status"] == "live"
    assert field["value"]["district"] == "Rural Residential/Agriculture"
    assert "Catskill" in field["source"]


def test_zoning_is_honest_for_greene_towns_without_gis(monkeypatch) -> None:
    """A Greene town outside Catskill (every mapped layer misses) falls back to an actionable
    reason, never a fabricated district."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.time, "sleep", lambda *_: None)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"features": []})
    prop = Property(name="Z", address="1 Rd", city="Windham", state="NY", county="Greene", latitude=42.297, longitude=-74.257)
    field = enrichment.ZoningProvider().fetch(prop)
    assert field["value"] is None
    assert "Catskill" in field["missing_reason"] and "zoning office" in field["missing_reason"]


def test_zoning_covers_a_sullivan_corridor_town(monkeypatch) -> None:
    """A Sullivan river-corridor town (e.g. Tusten/Narrowsburg) resolves a real district
    from the verified NPS Upper Delaware zoning layers."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"features": [{"attributes": {"ZONEID": "GR", "ZONENAME": "General Residential", "GENZONENAM": "Residential"}}]})
    prop = Property(name="Z", address="1 Main St", city="Narrowsburg", state="NY", county="Sullivan", latitude=41.603, longitude=-75.060)
    field = enrichment.ZoningProvider().fetch(prop)
    assert field["retrieval_status"] == "live"
    assert field["value"]["district"] == "GR" and field["value"]["description"] == "General Residential"
    assert "Upper Delaware" in field["source"]


def test_zoning_is_honest_for_monticello_outside_the_corridor_towns(monkeypatch) -> None:
    """Monticello (Town of Thompson) is not one of the mapped corridor towns; every corridor
    layer misses and the card falls back to an actionable reason — never a fabricated district."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.time, "sleep", lambda *_: None)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"features": []})
    monticello = Property(name="Z", address="1 Broadway", city="Monticello", state="NY", county="Sullivan", latitude=41.6556, longitude=-74.6893)
    field = enrichment.ZoningProvider().fetch(monticello)
    assert field["value"] is None
    assert "Monticello" in field["missing_reason"] and "zoning office" in field["missing_reason"]


def test_zoning_is_honest_for_delaware_county_with_no_gis(monkeypatch) -> None:
    """Delaware County NY has no zoning GIS at all — an actionable reason and no network call."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    def _forbidden(*_a, **_k): raise AssertionError("no HTTP call when there is no GIS source")
    monkeypatch.setattr(enrichment.HTTP, "get", _forbidden)
    delhi = Property(name="Z", address="1 Main St", city="Delhi", state="NY", county="Delaware", latitude=42.2784, longitude=-74.9160)
    field = enrichment.ZoningProvider().fetch(delhi)
    assert field["value"] is None and "Delaware County" in field["missing_reason"]


def test_zoning_raises_when_every_layer_fails_transiently(monkeypatch) -> None:
    """If all of a county's layers error out (no clean answer), the provider raises so a prior
    live fact is retained rather than overwritten with a false 'no zoning'."""
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.time, "sleep", lambda *_: None)
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *_a, **_k: {"error": {"code": 500}})
    prop = Property(name="Z", address="1 Main St", city="Narrowsburg", state="NY", county="Sullivan", latitude=41.603, longitude=-75.060)
    try:
        enrichment.ZoningProvider().fetch(prop)
        assert False, "expected ProviderError"
    except enrichment.ProviderError:
        pass


def test_zoning_provider_requires_coordinates(monkeypatch) -> None:
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    prop = Property(name="Z", address="1 Main St", city="New Paltz", state="NY", county="Ulster")
    field = enrichment.ZoningProvider().fetch(prop)
    assert field["value"] is None
    assert "Latitude and longitude" in field["missing_reason"]


def test_zoning_provider_retries_a_transient_error_then_succeeds(monkeypatch) -> None:
    from app.services import enrichment
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    monkeypatch.setattr(enrichment.time, "sleep", lambda *_: None)
    calls = {"n": 0}
    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1: return {"error": {"code": 500}}
        return {"features": [{"attributes": {"ZONE_CODE": "HC", "ZONE_DESC": "Hamlet Commercial", "ZONE_GENERAL": "Mixed Use", "YEAR": "2015"}}]}
    monkeypatch.setattr(enrichment.HTTP, "get", flaky)
    field = enrichment.ZoningProvider().fetch(_ulster_prop())
    assert calls["n"] == 2
    assert field["value"]["district"] == "HC"
