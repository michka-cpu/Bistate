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
        assert set(field) == {"value", "source", "retrieval_status", "last_updated", "confidence", "missing_reason"}


def test_import_requires_an_identifier(client: TestClient) -> None:
    assert client.post("/api/properties/import", json={}).status_code == 422


# ---- Regression: a normal manually-entered US address must import complete, not "manual/incomplete" ----

def test_full_street_address_with_city_state_zip_is_complete(client: TestClient) -> None:
    prop = client.post("/api/properties/import", json={"raw_address": "139 County Route 21c, Ghent, NY 12075"}).json()
    assert prop["listing_incomplete"] is False
    assert prop["city"] == "Ghent" and prop["state"] == "NY" and prop["postal_code"] == "12075"
    assert prop["status"] == "Reviewing"
    assert prop["name"] == "139 County Route 21c"


def test_abbreviated_road_forms_parse_completely(client: TestClient) -> None:
    for address, city, state in [
        ("88 Co Rd 9, Chatham, NY 12037", "Chatham", "NY"),
        ("77 County Route 21c, Ghent, NY 12075", "Ghent", "NY"),
        ("410 State Route 203, Valatie, NY", "Valatie", "NY"),
        ("12 Old Post Rd, Hudson, NY 12534", "Hudson", "NY"),
    ]:
        prop = client.post("/api/properties/import", json={"raw_address": address}).json()
        assert prop["listing_incomplete"] is False, address
        assert (prop["city"], prop["state"]) == (city, state), address


def test_duplicate_reentry_of_an_imported_address_returns_409_with_id(client: TestClient) -> None:
    first = client.post("/api/properties/import", json={"raw_address": "5 Diligence Way, Hudson, NY 12534"})
    assert first.status_code == 201
    again = client.post("/api/properties/import", json={"raw_address": "5 Diligence Way, Hudson, NY 12534"})
    assert again.status_code == 409
    assert f"id={first.json()['id']}" in again.json()["detail"]


def test_partial_address_without_locality_is_incomplete(client: TestClient) -> None:
    prop = client.post("/api/properties/import", json={"raw_address": "139 County Route 21c"}).json()
    assert prop["listing_incomplete"] is True
    assert prop["status"] == "Needs Info"


def test_full_address_listing_url_imports_complete(client: TestClient) -> None:
    prop = client.post("/api/properties/import", json={"listing_url": "https://www.zillow.com/homedetails/44-Maple-Ave-Hudson-NY-12534/700123_zpid/"}).json()
    assert prop["listing_incomplete"] is False
    assert prop["city"] == "Hudson" and prop["state"] == "NY"


def test_invalid_input_is_rejected(client: TestClient) -> None:
    # Whitespace-only text is not a usable identifier.
    assert client.post("/api/properties/import", json={"raw_address": "   "}).status_code == 422
    # A malformed URL fails validation.
    assert client.post("/api/properties/import", json={"listing_url": "notaurl"}).status_code == 422


def test_import_rejects_normalized_duplicate_address_and_url(client: TestClient) -> None:
    payload = {"raw_address": "139 County Route 21C, Ghent, NY"}
    assert client.post("/api/properties/import", json=payload).status_code == 201
    duplicate = client.post("/api/properties/import", json={"raw_address": "139 COUNTY ROUTE 21C, GHENT, ny"})
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]

    # A listing URL whose slug resolves to the same street address is now recognized as
    # the same property (previously the URL slug degraded to an opaque id and slipped through).
    same_via_url = {"listing_url": "https://www.zillow.com/homedetails/139-County-Route-21C-Ghent-NY/8675309_zpid/"}
    assert client.post("/api/properties/import", json=same_via_url).status_code == 409

    # A distinct listing URL imports once and is de-duplicated by URL on re-import.
    listing = {"listing_url": "https://www.zillow.com/homedetails/500-Distinct-Way-Ghent-NY-12075/123_zpid/"}
    assert client.post("/api/properties/import", json=listing).status_code == 201
    duplicate_url = client.post("/api/properties/import", json=listing)
    assert duplicate_url.status_code == 409


def test_import_marks_provider_id_only_urls_incomplete(client: TestClient) -> None:
    """A Zillow URL carrying only a zpid must not masquerade as a resolved address."""
    prop = client.post(
        "/api/properties/import",
        json={"listing_url": "https://www.zillow.com/homedetails/215394889_zpid/"},
    ).json()
    assert prop["listing_source"] == "Zillow"
    assert prop["listing_incomplete"] is True
    assert prop["status"] == "Needs Info"
    assert "215394889" in prop["name"]
    assert "Unknown" not in prop["name"]  # no fabricated locality in the name


def test_distinct_incomplete_listings_are_not_deduplicated(client: TestClient) -> None:
    """Two different zpid-only URLs share the Unknown/NA placeholder but are distinct
    properties; they must not collapse into one via the placeholder address."""
    first = client.post("/api/properties/import", json={"listing_url": "https://www.zillow.com/homedetails/111111_zpid/"})
    second = client.post("/api/properties/import", json={"listing_url": "https://www.zillow.com/homedetails/222222_zpid/"})
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    # The exact same URL is still rejected as a duplicate.
    assert client.post("/api/properties/import", json={"listing_url": "https://www.zillow.com/homedetails/111111_zpid/"}).status_code == 409


def test_redfin_and_realtor_urls_resolve_locality(client: TestClient) -> None:
    redfin = client.post("/api/properties/import", json={"listing_url": "https://www.redfin.com/NY/Hudson/50-Elm-St-12534/home/98765432"}).json()
    assert redfin["listing_incomplete"] is False
    assert redfin["city"] == "Hudson" and redfin["state"] == "NY"
    realtor = client.post("/api/properties/import", json={"listing_url": "https://www.realtor.com/realestateandhomes-detail/60-Oak-Ave_Kingston_NY_12401_M55555-11111"}).json()
    assert realtor["listing_incomplete"] is False
    assert realtor["city"] == "Kingston" and realtor["state"] == "NY"


def test_resolve_completes_an_incomplete_listing(client: TestClient) -> None:
    created = client.post(
        "/api/properties/import",
        json={"listing_url": "https://www.zillow.com/homedetails/998877_zpid/"},
    ).json()
    assert created["listing_incomplete"] is True
    resolved = client.post(
        f"/api/properties/{created['id']}/resolve",
        json={"raw_address": "77 Orchard Lane, Hudson, NY 12534"},
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["listing_incomplete"] is False
    assert body["address"] == "77 Orchard Lane"
    assert body["status"] == "Reviewing"


def test_import_rejects_duplicate_addresses_differing_only_by_punctuation_or_spacing(client: TestClient) -> None:
    assert client.post("/api/properties/import", json={"raw_address": "742 Evergreen Terrace, Springfield, NY 12345"}).status_code == 201
    for variant in (
        "742 Evergreen Terrace., Springfield, NY 12345",   # trailing punctuation
        "742  Evergreen  Terrace, Springfield, NY 12345",  # collapsed whitespace
        "742 EVERGREEN TERRACE, springfield, ny 12345",    # capitalization
        "742 Evergreen Terrace, Springfield, NY 12345",    # exact
    ):
        duplicate = client.post("/api/properties/import", json={"raw_address": variant})
        assert duplicate.status_code == 409, variant
        assert "already exists" in duplicate.json()["detail"]


def test_import_labels_landwatch_urls_with_their_provider(client: TestClient) -> None:
    prop = client.post(
        "/api/properties/import",
        json={"listing_url": "https://www.landwatch.com/columbia-county-new-york-land-for-sale/pid/123456"},
    )
    assert prop.status_code == 201
    assert prop.json()["listing_source"] == "LandWatch"


def test_financials_are_flagged_as_estimates_until_core_inputs_exist(client: TestClient) -> None:
    prop = client.post("/api/properties/import", json={"raw_address": "9 Estimate Rd, Hudson, NY 12534"}).json()
    # Without an asking price the workbook runs on defaults; the API must say so.
    assert prop["financials_are_estimates"] is True
    assert "asking_price" in prop["missing_core_inputs"]

    client.put(f"/api/properties/{prop['id']}", json={"asking_price": 640000})
    underwritten = client.post(f"/api/properties/{prop['id']}/underwrite")
    assert underwritten.status_code == 200
    refreshed = client.get(f"/api/properties/{prop['id']}").json()
    assert refreshed["financials_are_estimates"] is False
    assert "asking_price" not in refreshed["missing_core_inputs"]


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
