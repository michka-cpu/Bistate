"""Listing ingestion: real facts + provenance from a source, honest failure otherwise.

Deterministic — no live third-party sites. A representative Redfin-style page (canonical
schema.org JSON-LD + OpenGraph) is fed through the real parser via a mocked fetcher; block
and no-metadata cases are simulated by controlling the fetcher.
"""
from fastapi.testclient import TestClient

from app.services import enrichment, listing_ingestion
from app.services.listing_ingestion import (
    LISTING_FIELDS,
    ListingFetchError,
    extract_listing_facts,
    ingest_listing,
    provider_for,
)

# A compact but realistic listing page: canonical link, a Product with an Offer price,
# a SingleFamilyResidence with address/rooms/floorSize, and OpenGraph metadata.
REDFIN_HTML = """
<html><head>
<link rel="canonical" href="https://www.redfin.com/NY/Hudson/88-Union-St-12534/home/12345678"/>
<meta property="og:url" content="https://www.redfin.com/NY/Hudson/88-Union-St-12534/home/12345678"/>
<meta property="og:image" content="https://ssl.cdn-redfin.com/photo/88-union-front.jpg"/>
<meta property="og:description" content="4 beds, 2.5 baths, 2,100 sq. ft. single-family home located at 88 Union St, Hudson, NY 12534. View sales history and Redfin Estimate."/>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":["Product","RealEstateListing"],"name":"88 Union St",
 "url":"https://www.redfin.com/NY/Hudson/88-Union-St-12534/home/12345678",
 "offers":{"@type":"Offer","priceCurrency":"USD","price":625000,"availability":"https://schema.org/InStock"}}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"SingleFamilyResidence","name":"88 Union St",
 "url":"https://www.redfin.com/NY/Hudson/88-Union-St-12534/home/12345678",
 "address":{"@type":"PostalAddress","streetAddress":"88 Union St","addressLocality":"Hudson","addressRegion":"NY","postalCode":"12534","addressCountry":"US"},
 "numberOfRooms":4,"numberOfBathroomsTotal":2.5,"floorSize":{"@type":"QuantitativeValue","value":2100,"unitCode":"FTK"}}
</script>
</head><body>listing</body></html>
"""

REDFIN_URL = "https://www.redfin.com/NY/Hudson/88-Union-St-12534/home/12345678"


def _enable_live(monkeypatch):
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", True)
    # Keep enrichment (geocoding) hermetic: no real network for the property pipeline.
    monkeypatch.setattr(enrichment.HTTP, "get", lambda *a, **k: {})


# ---- Parser ----

def test_provider_recognition() -> None:
    assert provider_for("https://www.redfin.com/NY/Hudson/1-A-St/home/1") == "Redfin"
    assert provider_for("https://www.zillow.com/homedetails/1_zpid/") == "Zillow"
    assert provider_for("https://example.com/x") is None
    assert provider_for("http://") is None


def test_redfin_structured_metadata_is_parsed() -> None:
    facts, canonical = extract_listing_facts(REDFIN_HTML, REDFIN_URL, "Redfin")
    assert canonical.endswith("/home/12345678")
    assert facts["asking_price"]["value"] == 625000
    assert facts["bedrooms"]["value"] == 4
    assert facts["bathrooms"]["value"] == 2.5
    assert facts["square_feet"]["value"] == 2100
    assert facts["property_type"]["value"] == "Single Family"
    assert facts["listing_status"]["value"] == "For sale"
    assert facts["photos"]["value"] == ["https://ssl.cdn-redfin.com/photo/88-union-front.jpg"]
    # Every retrieved fact carries provenance.
    for key in ("asking_price", "bedrooms", "square_feet"):
        assert facts[key]["retrieval_status"] == "listing"
        assert facts[key]["source"] == "Redfin"
    # Fields the source did not publish are explicitly unavailable, not invented.
    assert facts["annual_taxes"]["value"] is None and facts["annual_taxes"]["retrieval_status"] == "unavailable"
    assert facts["acreage"]["value"] is None and facts["acreage"]["missing_reason"]
    # The listing's own address is captured (kept separate from identity resolution).
    assert facts["_address"]["city"] == "Hudson" and facts["_address"]["state"] == "NY"


# ---- ingest_listing status/honesty ----

def test_ingested_status_when_facts_retrieved(monkeypatch) -> None:
    _enable_live(monkeypatch)
    monkeypatch.setattr(listing_ingestion.HTTP, "get_html", lambda url: REDFIN_HTML)
    result = ingest_listing(REDFIN_URL)
    meta = result["_meta"]
    assert meta["status"] == "ingested" and meta["facts_retrieved"] is True
    assert "asking_price" in meta["fields_retrieved"]


def test_blocked_provider_fails_honestly(monkeypatch) -> None:
    _enable_live(monkeypatch)
    def blocked(url):
        raise ListingFetchError("provider blocked automated access (HTTP 403)", 403)
    monkeypatch.setattr(listing_ingestion.HTTP, "get_html", blocked)
    result = ingest_listing("https://www.zillow.com/homedetails/1-A-St/12_zpid/")
    meta = result["_meta"]
    assert meta["status"] == "blocked" and meta["facts_retrieved"] is False
    assert "403" in meta["reason"]
    # No listing facts are invented; each is unavailable with a clear reason.
    for field in LISTING_FIELDS:
        assert result[field]["value"] is None
        assert "licensed data API" in result[field]["missing_reason"]


def test_no_metadata_page_reports_no_facts(monkeypatch) -> None:
    _enable_live(monkeypatch)
    monkeypatch.setattr(listing_ingestion.HTTP, "get_html", lambda url: "<html><body>no data</body></html>")
    result = ingest_listing(REDFIN_URL)
    assert result["_meta"]["status"] == "no_metadata"
    assert result["_meta"]["facts_retrieved"] is False


def test_unsupported_and_disabled(monkeypatch) -> None:
    _enable_live(monkeypatch)
    assert ingest_listing("https://example.com/x")["_meta"]["status"] == "unsupported"
    # With live ingestion disabled, we never claim success.
    monkeypatch.setattr(enrichment.get_settings(), "live_providers_enabled", False)
    assert ingest_listing(REDFIN_URL)["_meta"]["status"] == "disabled"


# ---- Import flow ----

def test_import_populates_facts_and_opens_gate(client: TestClient, monkeypatch) -> None:
    _enable_live(monkeypatch)
    monkeypatch.setattr(listing_ingestion.HTTP, "get_html", lambda url: REDFIN_HTML)
    prop = client.post("/api/properties/import", json={"listing_url": REDFIN_URL}).json()
    # Real facts populate the underwriting columns.
    assert prop["asking_price"] == 625000
    assert prop["bedrooms"] == 4 and prop["bathrooms"] == 2.5 and prop["square_feet"] == 2100
    assert prop["property_type"] == "Single Family" and prop["listing_source"] == "Redfin"
    # Enough core facts exist -> the analysis-incomplete gate opens automatically.
    assert prop["analysis_incomplete"] is False
    assert prop["financials_are_estimates"] is False
    # Provenance is exposed and truthful.
    assert prop["listing_ingestion"]["status"] == "ingested"
    assert prop["listing_data"]["asking_price"]["source"] == "Redfin"
    assert prop["listing_data"]["annual_taxes"]["retrieval_status"] == "unavailable"


def test_blocked_import_stays_gated_and_honest(client: TestClient, monkeypatch) -> None:
    _enable_live(monkeypatch)
    def blocked(url):
        raise ListingFetchError("provider blocked automated access (HTTP 403)", 403)
    monkeypatch.setattr(listing_ingestion.HTTP, "get_html", blocked)
    prop = client.post("/api/properties/import", json={"listing_url": "https://www.zillow.com/homedetails/88-Union-St-Hudson-NY-12534/9_zpid/"}).json()
    # Address may resolve from the slug, but NO listing facts and the gate stays closed.
    assert prop["asking_price"] is None and prop["bedrooms"] is None
    assert prop["analysis_incomplete"] is True
    assert prop["listing_ingestion"]["facts_retrieved"] is False
    assert prop["listing_ingestion"]["provider"] == "Zillow"


def test_address_only_import_is_not_labeled_ingested(client: TestClient) -> None:
    # Regression: address/geocoder flow must not be mislabeled as listing ingestion.
    prop = client.post("/api/properties/import", json={"raw_address": "88 Union St, Hudson, NY 12534"}).json()
    assert prop["listing_ingestion"]["facts_retrieved"] is False
    assert prop["listing_ingestion"]["provider"] is None
    assert prop["listing_data"] == {}
    assert prop["analysis_incomplete"] is True
