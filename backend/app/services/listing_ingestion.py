"""Listing-fact ingestion.

Retrieves *real* listing-level facts for a pasted listing URL from legitimate sources —
the listing page's own published structured metadata (schema.org JSON-LD / OpenGraph),
or a licensed listing-data API when one is configured. Robots.txt is respected and only
the pasted detail page is read; nothing is scraped in violation of provider rules.

Honesty guarantees:
- A listing counts as *ingested* only when real listing facts are retrieved from a source.
- Resolving an address from the URL slug or geocoding it is NOT ingestion.
- When a provider blocks automated access (403/429) or exposes no listing metadata, every
  field is marked ``unavailable`` with a clear reason. Facts are never invented.
- Every retrieved fact carries provenance (source + retrieval status + URL + timestamp).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.config import get_settings

# The listing-level fields we attempt to retrieve, in report order.
LISTING_FIELDS = (
    "asking_price", "bedrooms", "bathrooms", "square_feet", "acreage", "property_type",
    "listing_status", "listing_date", "annual_taxes", "photos",
)

_SUPPORTED = {
    "zillow.com": "Zillow", "realtor.com": "Realtor", "redfin.com": "Redfin",
    "landwatch.com": "LandWatch", "airbnb.com": "Airbnb", "loopnet.com": "LoopNet",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetched(value: Any, source: str, url: str | None, confidence: float = 0.9) -> dict[str, Any]:
    """A listing fact genuinely retrieved from a source."""
    return {"value": value, "source": source, "retrieval_status": "listing",
            "confidence": confidence, "retrieved_at": now_iso(), "url": url, "missing_reason": None}


def unavailable(reason: str, source: str | None = None) -> dict[str, Any]:
    return {"value": None, "source": source, "retrieval_status": "unavailable",
            "confidence": 0, "retrieved_at": None, "url": None, "missing_reason": reason}


class ListingFetchError(Exception):
    """The listing page could not be retrieved (blocked, disallowed, or a network error)."""

    def __init__(self, reason: str, status: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status = status


class ListingHttpClient:
    """Polite HTML fetcher: respects robots.txt and reports blocks honestly."""

    def __init__(self) -> None:
        self._robots: dict[str, list[str]] = {}

    def get_html(self, url: str) -> str:
        settings = get_settings()
        if not self._robots_allows(url):
            raise ListingFetchError("The listing path is disallowed by the provider's robots.txt")
        request = Request(url, headers={
            "User-Agent": settings.listing_fetch_user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urlopen(request, timeout=settings.provider_timeout_seconds) as response:  # nosec B310
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", "ignore")
        except HTTPError as exc:
            if exc.code in (401, 403, 429):
                reason = f"provider blocked automated access (HTTP {exc.code})"
            elif exc.code == 404:
                reason = "listing not found (HTTP 404)"
            else:
                reason = f"provider returned HTTP {exc.code}"
            raise ListingFetchError(reason, exc.code) from exc
        except (URLError, TimeoutError) as exc:
            raise ListingFetchError("The listing page could not be reached") from exc

    def _robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc
        if host not in self._robots:
            self._robots[host] = self._load_disallows(f"{parsed.scheme}://{host}/robots.txt")
        path = parsed.path or "/"
        for rule in self._robots[host]:
            if rule.endswith("*"):
                if path.startswith(rule[:-1]):
                    return False
            elif path.startswith(rule):
                return False
        return True

    def _load_disallows(self, robots_url: str) -> list[str]:
        try:
            request = Request(robots_url, headers={"User-Agent": get_settings().listing_fetch_user_agent})
            with urlopen(request, timeout=get_settings().provider_timeout_seconds) as response:  # nosec B310
                text = response.read().decode("utf-8", "ignore")
        except Exception:
            return []  # No robots.txt reachable -> do not block on it.
        disallows: list[str] = []
        applies = False
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                applies = value == "*"
            elif key == "disallow" and applies and value:
                disallows.append(value)
        return disallows


HTTP = ListingHttpClient()


def provider_for(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for domain, name in _SUPPORTED.items():
        if host == domain or host.endswith(f".{domain}"):
            return name
    return None


def ingest_listing(url: str) -> dict[str, Any]:
    """Attempt to retrieve real listing facts for ``url``.

    Returns a mapping of ``field -> provenance`` for every LISTING_FIELDS entry plus a
    ``_meta`` summary describing whether facts were genuinely retrieved and why not.
    """
    provider = provider_for(url)
    if provider is None:
        return _result(None, "unsupported", "This site is not a supported listing provider.", url,
                       reason_for_fields="Unsupported provider.")
    if not get_settings().live_providers_enabled:
        return _result(provider, "disabled", "Live listing ingestion is disabled in this environment.", url,
                       reason_for_fields="Live listing ingestion is disabled.")

    settings = get_settings()
    # Prefer a licensed listing-data API when configured (documented, permitted).
    if settings.listing_data_api_key:
        # No licensed connector is wired in this build; report honestly rather than inventing.
        return _result(provider, "no_connector",
                       f"A licensed listing-data API key is configured but no {provider} connector is enabled in this build.",
                       url, reason_for_fields="Licensed connector not enabled.")

    # Otherwise read the listing page's own published structured metadata.
    try:
        html = HTTP.get_html(url)
    except ListingFetchError as exc:
        status = "not_found" if exc.status == 404 else "blocked"
        field_reason = (f"{provider} listing not found — {exc.reason}." if exc.status == 404
                        else f"{provider} {exc.reason}; a licensed data API is required to read its listing facts.")
        return _result(provider, status, f"{provider} did not return listing metadata: {exc.reason}", url,
                       reason_for_fields=field_reason)

    facts, canonical = extract_listing_facts(html, url, provider)
    if not any(item.get("value") is not None for item in facts.values()):
        return _result(provider, "no_metadata",
                       f"{provider} returned a page but no machine-readable listing metadata was found.",
                       canonical or url, reason_for_fields="No structured listing metadata was published on the page.")

    retrieved = [key for key, item in facts.items() if item.get("value") is not None]
    result = dict(facts)
    result["_meta"] = {
        "provider": provider, "status": "ingested", "facts_retrieved": True,
        "fields_retrieved": retrieved, "reason": None,
        "canonical_url": canonical or url, "fetched_at": now_iso(),
    }
    return result


def _result(provider: str | None, status: str, reason: str, url: str, reason_for_fields: str) -> dict[str, Any]:
    """Build an all-unavailable result with a per-field reason and a status summary."""
    result: dict[str, Any] = {field: unavailable(reason_for_fields, provider) for field in LISTING_FIELDS}
    result["_meta"] = {
        "provider": provider, "status": status, "facts_retrieved": False,
        "fields_retrieved": [], "reason": reason, "canonical_url": url, "fetched_at": now_iso(),
    }
    return result


# ---- Structured-metadata extraction (schema.org JSON-LD + OpenGraph) ----

_TYPE_LABELS = {
    "singlefamilyresidence": "Single Family", "house": "Single Family", "residence": "Residence",
    "apartment": "Apartment", "apartmentcomplex": "Apartment", "condominium": "Condo",
    "accommodation": "Residence", "product": None, "landparcel": "Land",
}


def extract_listing_facts(html: str, url: str, provider: str) -> tuple[dict[str, Any], str | None]:
    canonical = _canonical_url(html) or url
    objects = _json_ld_objects(html)
    # A listing's facts are often split across sibling JSON-LD objects (a Product carrying
    # the Offer price, a Residence carrying rooms/address). Merge across all objects that
    # belong to this listing, taking the first non-null for each field.
    matching = _matching_objects(objects, canonical)
    og = _open_graph(html)

    src = provider

    def put(field: str, value: Any, conf: float = 0.9) -> tuple[str, dict[str, Any]]:
        return field, (fetched(value, src, canonical, conf) if value is not None
                       else unavailable(f"{provider} did not publish {field.replace('_', ' ')} in its listing metadata.", provider))

    def first(fn):
        for obj in matching:
            value = fn(obj)
            if value is not None:
                return value
        return None

    price = first(_extract_price)
    address = first(lambda o: o.get("address") if isinstance(o.get("address"), dict) else None) or _og_address(og)
    beds = first(lambda o: _extract_number(o, ("numberOfBedrooms", "numberOfRooms")))
    baths = first(lambda o: _extract_number(o, ("numberOfBathroomsTotal", "numberOfBathrooms")))
    sqft = first(_extract_floor_size)
    ptype = first(lambda o: _extract_property_type(o, og))
    status = first(_extract_status)
    photo = _extract_photo(matching[0] if matching else None, og)

    # OpenGraph description commonly restates the *main* listing's beds/baths/sqft; use it
    # as a cross-source fallback when JSON-LD (which may describe a nearby home) is absent.
    og_beds, og_baths, og_sqft = _parse_og_summary(og.get("description"))
    beds = beds if beds is not None else og_beds
    baths = baths if baths is not None else og_baths
    sqft = sqft if sqft is not None else og_sqft

    facts = dict([
        put("asking_price", price),
        put("bedrooms", beds),
        put("bathrooms", baths),
        put("square_feet", sqft),
        put("acreage", first(_extract_lot_acres)),
        put("property_type", ptype),
        put("listing_status", status),
        put("listing_date", first(_extract_date)),
        put("annual_taxes", None),  # not exposed in schema.org listing metadata
        put("photos", [photo] if photo else None),
    ])
    # Carry the address the metadata reported (kept separate; identity resolution owns city/state).
    if isinstance(address, dict):
        facts["_address"] = {
            "street": address.get("streetAddress"), "city": address.get("addressLocality"),
            "state": address.get("addressRegion"), "postal_code": address.get("postalCode"),
        }
    return facts, canonical


def _json_ld_objects(html: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if "@graph" in item and isinstance(item["@graph"], list):
                    stack.extend(item["@graph"])
                objects.append(item)
    return objects


def _types(obj: dict[str, Any]) -> list[str]:
    t = obj.get("@type")
    return [str(x).lower() for x in (t if isinstance(t, list) else [t] if t else [])]


def _home_id(url: str | None) -> str | None:
    m = re.search(r"/home/(\d+)", url or "")
    return m.group(1) if m else None


_RESIDENCE_TYPES = {"singlefamilyresidence", "house", "residence", "apartment",
                    "accommodation", "condominium", "place", "realestatelisting", "product"}


def _matching_objects(objects: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    """All JSON-LD objects belonging to the canonical listing (same /home/<id>).

    Falls back to an unambiguous single-residence page when the page has no home id."""
    home_id = _home_id(canonical)
    if home_id:
        matched = [o for o in objects if _home_id(o.get("url")) == home_id]
        if matched:
            return matched
    residences = [o for o in objects if (set(_types(o)) & _RESIDENCE_TYPES) and (o.get("address") or o.get("offers"))]
    if len(residences) == 1:
        return residences
    # Ambiguous page: only trust an object that itself carries address+offers together.
    return [o for o in objects if o.get("address") and o.get("offers")]


def _extract_price(listing: dict[str, Any] | None) -> float | None:
    if not isinstance(listing, dict):
        return None
    offers = listing.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    for key in ("price", "lowPrice", "highPrice"):
        value = offers.get(key) if isinstance(offers, dict) else None
        if value is None:
            value = listing.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
        if isinstance(value, str):
            digits = re.sub(r"[^\d.]", "", value)
            if digits:
                try:
                    return float(digits)
                except ValueError:
                    pass
    return None


def _extract_number(listing: dict[str, Any] | None, keys: tuple[str, ...]) -> float | None:
    if not isinstance(listing, dict):
        return None
    for key in keys:
        value = listing.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)?", value.strip()):
            return float(value)
    return None


def _extract_floor_size(listing: dict[str, Any] | None) -> int | None:
    if not isinstance(listing, dict):
        return None
    size = listing.get("floorSize")
    value = size.get("value") if isinstance(size, dict) else size
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if digits:
            return int(digits)
    return None


def _extract_lot_acres(listing: dict[str, Any] | None) -> float | None:
    if not isinstance(listing, dict):
        return None
    lot = listing.get("lotSize") or listing.get("lot")
    value = lot.get("value") if isinstance(lot, dict) else lot
    unit = (lot.get("unitText") or lot.get("unitCode") or "") if isinstance(lot, dict) else ""
    if isinstance(value, (int, float)):
        if re.search(r"acre", str(unit), re.I):
            return round(float(value), 3)
        if re.search(r"(FTK|sqft|SquareFoot|square)", str(unit), re.I) and value > 0:
            return round(float(value) / 43560.0, 3)
    return None


def _extract_property_type(listing: dict[str, Any] | None, og: dict[str, str]) -> str | None:
    for t in _types(listing or {}):
        if t in _TYPE_LABELS and _TYPE_LABELS[t]:
            return _TYPE_LABELS[t]
    desc = (og.get("description") or "").lower()
    for needle, label in (("single-family", "Single Family"), ("single family", "Single Family"),
                          ("condo", "Condo"), ("townhouse", "Townhouse"), ("multi-family", "Multi-Family"),
                          ("land", "Land"), ("farm", "Farm")):
        if needle in desc:
            return label
    return None


def _extract_status(listing: dict[str, Any] | None) -> str | None:
    if not isinstance(listing, dict):
        return None
    offers = listing.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    availability = offers.get("availability") if isinstance(offers, dict) else None
    if not availability:
        return None
    token = str(availability).rsplit("/", 1)[-1].lower()
    return {"instock": "For sale", "limitedavailability": "For sale",
            "outofstock": "Off market", "soldout": "Sold", "discontinued": "Off market"}.get(token)


def _extract_date(listing: dict[str, Any] | None) -> str | None:
    if not isinstance(listing, dict):
        return None
    for key in ("datePosted", "availabilityStarts", "dateModified"):
        value = listing.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_photo(listing: dict[str, Any] | None, og: dict[str, str]) -> str | None:
    image = og.get("image")
    if isinstance(image, str) and image and "logo" not in image.lower():
        return image
    if isinstance(listing, dict):
        photo = listing.get("image") or (listing.get("photo") or {})
        if isinstance(photo, list):
            photo = photo[0] if photo else None
        if isinstance(photo, dict):
            photo = photo.get("url") or photo.get("contentUrl")
        if isinstance(photo, str) and "logo" not in photo.lower():
            return photo
    return None


def _canonical_url(html: str) -> str | None:
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    return m.group(1) if m else None


def _open_graph(html: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for prop, content in re.findall(r'<meta[^>]+property=["\']og:([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']', html, re.I):
        tags.setdefault(prop.lower(), content)
    return tags


def _parse_og_summary(description: str | None) -> tuple[float | None, float | None, int | None]:
    if not description:
        return None, None, None
    beds = _search_num(r"([\d.]+)\s*beds?", description)
    baths = _search_num(r"([\d.]+)\s*baths?", description)
    sqft_m = re.search(r"([\d,]+)\s*sq\.?\s*ft", description, re.I)
    sqft = int(sqft_m.group(1).replace(",", "")) if sqft_m else None
    return beds, baths, sqft


def _search_num(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.I)
    return float(m.group(1)) if m else None


def _og_address(og: dict[str, str]) -> dict[str, str] | None:
    """Recover the listing's address from an OpenGraph description ('… located at ADDR.')
    when JSON-LD carries no PostalAddress — so identity follows the retrieved facts."""
    description = og.get("description") or ""
    match = re.search(r"located at\s+(.+?)(?:\.\s|\.$|$)", description, re.I)
    if not match:
        return None
    parts = [part.strip() for part in match.group(1).split(",") if part.strip()]
    if len(parts) < 3 or not re.match(r"^\s*\d+\s+\S", parts[0]):
        return None
    state_zip = parts[2].split()
    return {
        "streetAddress": parts[0], "addressLocality": parts[1],
        "addressRegion": state_zip[0] if state_zip else None,
        "postalCode": state_zip[1] if len(state_zip) > 1 else None,
    }


# ---- Applying retrieved facts to a property (keeps listing/identity/enrichment distinct) ----

# Listing fields that feed the underwriting columns. Populated only from genuinely
# retrieved values, and never overwriting an existing (user-supplied) value.
_CORE_COLUMNS = ("asking_price", "bedrooms", "bathrooms", "square_feet", "acreage",
                 "property_type", "listing_status", "annual_taxes")


def apply_listing_facts(prop: Any, listing_data: dict[str, Any]) -> str:
    """Persist listing provenance and fill real facts onto the property. Returns the
    ingestion status. Identity (city/state) is only backfilled from the listing's own
    published address when it is still a placeholder — geocoding remains the resolver."""
    address = listing_data.get("_address") or {}
    prop.listing_data = {key: value for key, value in listing_data.items() if key != "_address"}

    for field in _CORE_COLUMNS:
        item = listing_data.get(field) or {}
        value = item.get("value")
        if value is not None and getattr(prop, field, None) is None:
            setattr(prop, field, value)

    photos = (listing_data.get("photos") or {}).get("value")
    if photos and not (prop.images or []):
        prop.images = [url for url in photos if url]

    facts_retrieved = bool((listing_data.get("_meta") or {}).get("facts_retrieved"))
    if isinstance(address, dict) and address.get("street") and facts_retrieved:
        # The listing's own published address is authoritative for the retrieved facts —
        # use it as the identity so a provider redirect can't attach facts to a different
        # (slug-derived) address. Only applied when facts were genuinely ingested.
        prop.address = str(address["street"])
        prop.name = str(address["street"])
        if address.get("city"):
            prop.city = str(address["city"])
        if address.get("state"):
            prop.state = str(address["state"])[:2].upper()
        if address.get("postal_code"):
            prop.postal_code = str(address["postal_code"])
    elif isinstance(address, dict):
        # No usable listing address (or nothing ingested): only backfill placeholders,
        # leaving identity resolution to the slug + geocoder.
        if address.get("postal_code") and not prop.postal_code:
            prop.postal_code = str(address["postal_code"])
        if address.get("city") and (prop.city or "") in ("", "Unknown"):
            prop.city = str(address["city"])
        if address.get("state") and (prop.state or "").upper() in ("", "NA"):
            prop.state = str(address["state"])[:2].upper()

    return (listing_data.get("_meta") or {}).get("status", "unknown")
