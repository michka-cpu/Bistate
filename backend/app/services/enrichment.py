"""Production-safe public-data enrichment adapters with a stable API contract."""
from __future__ import annotations

import json
import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
"""Resilient, provenance-first live-data provider registry.

The legacy enrichment keys remain part of the public acquisition contract. Every run
returns every key, even when an adapter is unavailable or has failed.
"""

from app.config import get_settings
from app.models.property import Property

logger = logging.getLogger(__name__)
STALE_AFTER = timedelta(days=30)
NYC_ORIGIN = "21 W 38th St, New York, NY"


def now() -> datetime: return datetime.now(timezone.utc)


def unavailable(reason: str, source: str | None = None) -> dict[str, Any]:
    return {"value": None, "source": source, "retrieval_status": "unavailable", "confidence": 0, "last_updated": None, "missing_reason": reason}


def live(value: Any, source: str, confidence: float = 0.9) -> dict[str, Any]:
    return {"value": value, "source": source, "retrieval_status": "live", "confidence": confidence, "last_updated": now().isoformat(), "missing_reason": None}


class ProviderError(Exception): pass
class RateLimitError(ProviderError): pass


class JsonHttpClient:
    """Small, dependency-free HTTP client with bounded retries and rate-limit handling."""
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], tuple[float, Any]] = {}

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        settings = get_settings()
        cache_key = (url, urlencode(sorted((params or {}).items()), doseq=True))
        cached = self._cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        url = f"{url}?{urlencode(params, doseq=True)}" if params else url
        for attempt in range(settings.provider_retry_count + 1):
            try:
                request = Request(url, headers={"Accept": "application/json", "User-Agent": "Bistate/1.0"})
                with urlopen(request, timeout=settings.provider_timeout_seconds) as response:  # nosec B310: configured public APIs
                    result = json.loads(response.read().decode())
                    # Do not cache ArcGIS/JSON error envelopes (HTTP 200 with an "error"
                    # key), or a transient provider failure would be pinned for the whole
                    # cache TTL and defeat the refresh/retry path.
                    if not (isinstance(result, dict) and "error" in result):
                        self._cache[cache_key] = (time.monotonic() + settings.provider_cache_seconds, result)
                    return result
            except HTTPError as exc:
                if exc.code == 429 and attempt < settings.provider_retry_count:
                    time.sleep(min(2**attempt, 4)); continue
                if exc.code == 429: raise RateLimitError("Provider rate limit exceeded") from exc
                raise ProviderError(f"Provider returned HTTP {exc.code}") from exc
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt < settings.provider_retry_count:
                    time.sleep(min(2**attempt, 4)); continue
                raise ProviderError("Provider request failed or returned malformed JSON") from exc


HTTP = JsonHttpClient()
PROVIDER_DIAGNOSTICS: dict[str, dict[str, Any]] = {}


class Provider(Protocol):
    key: str
    source: str
    required_setting: str | None
    def fetch(self, prop: Property) -> dict[str, Any]: ...


def _clean_county(name: str | None) -> str | None:
    """Return a county name without the trailing 'County'/'Parish' descriptor."""
    if not name: return None
    return re.sub(r"\s+(County|Parish|Borough|Census Area)$", "", name.strip(), flags=re.IGNORECASE) or None


def _is_placeholder_city(value: str | None) -> bool:
    return (value or "").strip() in ("", "Unknown")


def _is_placeholder_state(value: str | None) -> bool:
    return (value or "").strip().upper() in ("", "NA")


class CensusGeocoder:
    """Keyless public geocoder. A single request resolves coordinates *and* census
    geographies (county, tract, ZIP), which are persisted onto the property so a normal
    address auto-populates its structured identity."""
    key, source, required_setting = "geocoding", "U.S. Census Geocoder", None
    def fetch(self, prop: Property) -> dict[str, Any]:
        if not get_settings().live_providers_enabled: return unavailable("Live public providers are disabled")
        # Build the query from the street plus only *real* locality values. Placeholder
        # city/state (Unknown/NA left by an imperfect parse) would otherwise pollute the
        # query and prevent a match, so they are dropped and the geocoder recovers them.
        query_city = None if _is_placeholder_city(prop.city) else prop.city
        query_state = None if _is_placeholder_state(prop.state) else prop.state
        address = ", ".join(filter(None, [prop.address, query_city, query_state, prop.postal_code]))
        data = HTTP.get("https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress", {"address": address, "benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"})
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches: return unavailable("Address was not matched by the U.S. Census Geocoder")
        match = matches[0]
        coordinates = match.get("coordinates", {})
        if not {"x", "y"} <= coordinates.keys(): return unavailable("Geocoder response did not include coordinates")
        prop.longitude, prop.latitude = coordinates["x"], coordinates["y"]
        components = match.get("addressComponents", {})
        geographies = match.get("geographies", {})
        county_name = ((geographies.get("Counties") or [{}])[0]).get("NAME")
        tract = (geographies.get("Census Tracts") or [{}])[0]
        subdivision = ((geographies.get("County Subdivisions") or [{}])[0]).get("NAME")
        # Backfill verified structured facts from the authoritative match. Placeholder
        # locality values are corrected; real user-entered values are never overwritten.
        zip_code = components.get("zip")
        matched_city, matched_state = components.get("city"), components.get("state")
        if zip_code and not prop.postal_code: prop.postal_code = zip_code
        if matched_city and _is_placeholder_city(prop.city): prop.city = matched_city.title()
        if matched_state and _is_placeholder_state(prop.state): prop.state = matched_state.upper()[:2]
        cleaned_county = _clean_county(county_name)
        if cleaned_county and not prop.county: prop.county = cleaned_county
        # Stash the resolved geography so the demographics adapter can reuse it in-run.
        prop._census_geography = {"state": tract.get("STATE"), "county": tract.get("COUNTY"), "tract": tract.get("TRACT")}  # type: ignore[attr-defined]
        return live({
            "latitude": prop.latitude, "longitude": prop.longitude,
            "matched_address": match.get("matchedAddress"),
            "zip": zip_code, "county": cleaned_county, "town": subdivision,
            "census_tract": tract.get("TRACT"), "state_fips": tract.get("STATE"), "county_fips": tract.get("COUNTY"),
        }, self.source, 0.95)


class FemaFloodProvider:
    key, source, required_setting = "fema_flood", "FEMA National Flood Hazard Layer", None
    url = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
    def fetch(self, prop: Property) -> dict[str, Any]:
        if not get_settings().live_providers_enabled: return unavailable("Live public providers are disabled")
        if prop.latitude is None or prop.longitude is None: return unavailable("Latitude and longitude are required for FEMA flood lookup")
        point = f"{prop.longitude},{prop.latitude}"
        params = {"geometry": point, "geometryType": "esriGeometryPoint", "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "FLD_ZONE,FLD_ZONE_SUBTY,SFHA_TF", "returnGeometry": "false", "f": "json"}
        # FEMA's public NFHL ArcGIS endpoint intermittently returns HTTP 200 with an
        # {"error": …} envelope when rate-limiting or degraded. Retry with backoff before
        # giving up; a flood determination is never fabricated on failure.
        last_reason = ""
        for attempt in range(3):
            data = HTTP.get(self.url, params)
            if isinstance(data, dict) and data.get("error"):
                last_reason = f"error {data['error'].get('code', '')}"
            elif not isinstance(data.get("features"), list):
                last_reason = "response did not include features"
            else:
                features = data["features"]
                if not features:
                    return live({"flood_zone": None, "flood_risk": "outside_mapped_special_flood_hazard_area", "map_panel": None}, self.source, 0.8)
                attrs = features[0].get("attributes", {})
                zone = attrs.get("FLD_ZONE")
                return live({"flood_zone": zone, "flood_risk": "special_flood_hazard_area" if attrs.get("SFHA_TF") == "T" else "mapped", "map_panel": attrs.get("FLD_ZONE_SUBTY")}, self.source, 0.9)
            if attempt < 2:
                time.sleep(min(2 ** attempt, 4))
        raise ProviderError(f"FEMA flood service is temporarily unavailable ({last_reason})")


class CensusDemographicsProvider:
    """ACS 5-year tract demographics. The ACS *data* API now requires a free Census key
    (the geocoder/geographies calls remain keyless), so this adapter is honestly
    unavailable until ``census_api_key`` is configured."""
    key, source, required_setting = "census_demographics", "U.S. Census Bureau ACS 5-Year API", "census_api_key"
    def fetch(self, prop: Property) -> dict[str, Any]:
        settings = get_settings()
        if not settings.live_providers_enabled: return unavailable("Live public providers are disabled")
        if not settings.census_api_key: return unavailable("A free Census API key is required for ACS demographics (set census_api_key)")
        if prop.latitude is None or prop.longitude is None: return unavailable("Latitude and longitude are required for Census geography lookup")
        state, county, tract_code = self._resolve_geography(prop)
        if not all((state, county, tract_code)): return unavailable("Census tract was not available for coordinates")
        variables = "NAME,B01003_001E,B19013_001E,B01002_001E,B25002_001E,B25003_002E,B25003_003E"
        rows = HTTP.get("https://api.census.gov/data/2023/acs/acs5", {"get": variables, "for": f"tract:{tract_code}", "in": [f"state:{state}", f"county:{county}"], "key": settings.census_api_key})
        if not isinstance(rows, list) or len(rows) < 2: return unavailable("Census ACS response contained no tract data")
        headers, values = rows[0], rows[1]; record = dict(zip(headers, values))
        def number(key: str) -> int | None:
            try: return int(record[key])
            except (KeyError, TypeError, ValueError): return None
        occupied, owner, renter = number("B25002_001E"), number("B25003_002E"), number("B25003_003E")
        return live({"geography": {"state": state, "county": county, "tract": tract_code}, "population": number("B01003_001E"), "median_household_income": number("B19013_001E"), "median_age": number("B01002_001E"), "housing_occupancy": occupied, "owner_occupied": owner, "renter_occupied": renter}, self.source, 0.9)

    @staticmethod
    def _resolve_geography(prop: Property) -> tuple[str | None, str | None, str | None]:
        # Reuse the geography the geocoder already resolved this run, if present.
        cached = getattr(prop, "_census_geography", None)
        if cached and all(cached.get(part) for part in ("state", "county", "tract")):
            return cached["state"], cached["county"], cached["tract"]
        geo = HTTP.get("https://geocoding.geo.census.gov/geocoder/geographies/coordinates", {"x": prop.longitude, "y": prop.latitude, "benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"})
        tract = ((geo.get("result", {}).get("geographies", {}) or {}).get("Census Tracts") or [{}])[0]
        return tract.get("STATE"), tract.get("COUNTY"), tract.get("TRACT")


class ElevationProvider:
    """Keyless USGS elevation point query — verifiable terrain context for any coordinate."""
    key, source, required_setting = "elevation", "USGS EPQS (The National Map)", None
    url = "https://epqs.nationalmap.gov/v1/json"
    def fetch(self, prop: Property) -> dict[str, Any]:
        if not get_settings().live_providers_enabled: return unavailable("Live public providers are disabled")
        if prop.latitude is None or prop.longitude is None: return unavailable("Latitude and longitude are required for elevation lookup")
        data = HTTP.get(self.url, {"x": prop.longitude, "y": prop.latitude, "units": "Feet", "wkid": 4326, "includeDate": "false"})
        try:
            elevation = round(float(data.get("value")), 1)
        except (TypeError, ValueError):
            return unavailable("Elevation service did not return a numeric value")
        return live({"elevation_feet": elevation, "datum": "NAVD88"}, self.source, 0.85)


def _attr(attrs: dict[str, Any], field: str | None) -> Any:
    """Read an ArcGIS attribute by a (possibly absent) field name; blanks become None."""
    if not field: return None
    value = attrs.get(field)
    text = "" if value is None else str(value).strip()
    return text or None


# Public, keyless county zoning GIS layers. Every layer here is REAL and verified —
# point-queried live, with its field names confirmed against the actual response. Each
# county maps to an ordered list of zoning-district polygon layers (usually one; several
# where a county has no single county-wide layer). The provider tries them in turn and
# returns the first district the point falls inside. Keys are lowercase county names (no
# "County" suffix). First market: the Catskills (NY).
_UPDE = "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/UPDE_BND_TownZoning_ply/FeatureServer"
ZONING_GIS_SOURCES: dict[str, list[dict[str, Any]]] = {
    # Ulster: a single clean county-wide layer maintained by the county planning board.
    "ulster": [{
        "url": "https://gis.ulstercountyny.gov/server/rest/services/Parcel_Viewer/Municipal_Zoning/MapServer/33/query",
        "name": "Ulster County Planning Board zoning (public ArcGIS)",
        "code_field": "ZONE_CODE",        # e.g. "B-2", "HC", "R-2"
        "desc_field": "ZONE_DESC",        # e.g. "Core Business", "Hamlet Commercial"
        "general_field": "ZONE_GENERAL",  # coarse category, e.g. "Business", "Mixed Use"
        "year_field": "YEAR",             # town-submitted map vintage (mixed)
    }],
    # Sullivan: no county-wide layer exists. The National Park Service Upper Delaware set
    # publishes verified zoning polygons for six river-corridor towns ONLY (not the Town of
    # Thompson/Monticello or the county interior). Field names differ per town — each layer
    # carries its own mapping — and the map vintage is baked into the source label. A point
    # outside all six falls through to the honest ZONING_NO_PUBLIC_GIS reason below.
    "sullivan": [
        {"url": f"{_UPDE}/0/query", "name": "NPS Upper Delaware — Town of Cochecton zoning (2013)", "code_field": "ZONEID", "desc_field": "ZONENAME", "general_field": "GENZONENAM"},
        {"url": f"{_UPDE}/2/query", "name": "NPS Upper Delaware — Town of Delaware zoning (2013)", "code_field": "ZONEID", "desc_field": "ZONENAME", "general_field": "GENZONENAM"},
        {"url": f"{_UPDE}/3/query", "name": "NPS Upper Delaware — Town of Fremont zoning (2008)", "code_field": "Desig", "desc_field": "Zone_"},
        {"url": f"{_UPDE}/5/query", "name": "NPS Upper Delaware — Town of Lumberland zoning (2016)", "code_field": "Dist_Code", "desc_field": "District_N"},
        {"url": f"{_UPDE}/8/query", "name": "NPS Upper Delaware — Town of Highland zoning (2014)", "code_field": "ZONEID", "desc_field": "ZONENAME", "general_field": "GENZONENAM"},
        {"url": f"{_UPDE}/9/query", "name": "NPS Upper Delaware — Town of Tusten zoning (2013)", "code_field": "ZONEID", "desc_field": "ZONENAME", "general_field": "GENZONENAM"},
    ],
}

# Catskills counties investigated with NO queryable public zoning GIS beyond what is mapped
# above — only static PDF/eCode maps (confirmed for the Sullivan interior incl. the Town of
# Thompson/Monticello, and for all of Delaware County NY). When a point matches no mapped
# layer, the card states this honest, actionable reason rather than inventing a district.
ZONING_NO_PUBLIC_GIS: dict[str, str] = {
    "sullivan": "This point is outside the six Upper Delaware corridor towns Bistate maps in Sullivan County. The rest of the county — including the Town of Thompson (Monticello) — publishes zoning only as static maps; confirm the district with the town zoning office.",
    "delaware": "Delaware County (NY) publishes no public zoning GIS layer, only static town maps. Confirm the district with the town zoning office.",
}


class ZoningProvider:
    """Keyless municipal-zoning lookup for supported markets.

    US zoning is administered per-municipality and has no national API, so this provider
    queries a registry of *verified* public ArcGIS zoning-district layers by point-in-polygon
    — the same technique as the FEMA flood lookup — trying each of a county's layers until the
    point falls inside a district. Where no layer matches (an unzoned area, or a county that
    publishes only static maps) it reports an honest "unavailable" and never invents a
    district."""
    key, source, required_setting = "zoning", "County zoning GIS (public ArcGIS)", None

    def fetch(self, prop: Property) -> dict[str, Any]:
        if not get_settings().live_providers_enabled: return unavailable("Live public providers are disabled")
        if prop.latitude is None or prop.longitude is None: return unavailable("Latitude and longitude are required for a zoning lookup")
        county = _clean_county(prop.county)
        key = (county or "").lower()
        layers = ZONING_GIS_SOURCES.get(key)
        if not layers:
            reason = ZONING_NO_PUBLIC_GIS.get(key)
            if not reason:
                where = f"{county} County" if county else "this location"
                reason = f"No public zoning GIS service is mapped for {where} yet (outside supported markets)"
            return unavailable(reason)
        params = {"geometry": f"{prop.longitude},{prop.latitude}", "geometryType": "esriGeometryPoint", "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "false", "f": "json"}
        saw_clean_miss = False
        for layer in layers:
            outcome = self._query_layer(layer, params)
            if isinstance(outcome, dict):
                return live(outcome, layer["name"], 0.85)
            if outcome == "miss":
                saw_clean_miss = True
        # No layer's polygon contained the point. If at least one layer answered cleanly
        # (an honest miss), report that; if every layer failed transiently, raise so a prior
        # live fact is retained rather than overwritten with a false "no zoning".
        if not saw_clean_miss:
            raise ProviderError("County zoning service is temporarily unavailable")
        fallback = ZONING_NO_PUBLIC_GIS.get(key)
        return unavailable(fallback or f"Coordinates fall outside a mapped zoning district in {county} County", self.source)

    def _query_layer(self, layer: dict[str, Any], params: dict[str, Any]) -> dict[str, Any] | str:
        """Query one zoning layer. Returns the district dict on a hit, the string "miss" on a
        clean empty/uncoded response, or "error" if the layer failed after retries."""
        for attempt in range(3):
            data = HTTP.get(layer["url"], params)
            if isinstance(data, dict) and data.get("error"):
                pass
            elif not isinstance(data.get("features"), list):
                pass
            else:
                features = data["features"]
                if not features:
                    return "miss"
                code = _attr(features[0].get("attributes", {}), layer["code_field"])
                if not code:
                    return "miss"
                attrs = features[0].get("attributes", {})
                return {"district": code, "description": _attr(attrs, layer.get("desc_field")), "category": _attr(attrs, layer.get("general_field")), "as_of": _attr(attrs, layer.get("year_field"))}
            if attempt < 2:
                time.sleep(min(2 ** attempt, 4))
        return "error"


class ConfiguredProvider:
    def __init__(self, key: str, source: str, required_setting: str | None): self.key, self.source, self.required_setting = key, source, required_setting
    def fetch(self, prop: Property) -> dict[str, Any]:
        configured = bool(self.required_setting and getattr(get_settings(), self.required_setting, None))
        return unavailable("Provider credentials are not configured" if not configured else "Live connector is not enabled for this provider")


class SuitabilityProvider:
    required_setting = None
    def __init__(self, key: str, resolver): self.key, self.source, self.resolver = key, "Bistate suitability model", resolver
    def fetch(self, prop: Property) -> dict[str, Any]:
        value = self.resolver(prop)
        return unavailable("Required property facts are unavailable") if value is None else live(value, self.source, 0.65)


def _wedding(prop: Property) -> int | None: return min(100, round(45 + prop.acreage * 12)) if prop.acreage is not None else None
def _airbnb(prop: Property) -> int | None: return min(100, round(45 + prop.bedrooms * 7 + (prop.bathrooms or 0) * 4)) if prop.bedrooms is not None else None


# ---- Keyless location enrichment: OpenStreetMap (Overpass) POIs + OSRM routing ----
# Once coordinates exist these run automatically with no API key. A single Overpass query
# and a single OSRM table call cover every access fact; results are memoized on the
# property so the per-field providers reuse them without re-hitting the network.

OSM_SOURCE = "OpenStreetMap (Overpass) + OSRM public routing"
# Multiple public Overpass mirrors: rotate on rate-limit/timeout so a busy primary does
# not drop location facts. All are the same public OSM data, queried politely.
OVERPASS_URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
OSRM_URL = "https://router.project-osrm.org/table/v1/driving"
NYC_LATLON = (40.7484, -73.9857)  # Midtown Manhattan

# key -> (overpass selectors, radius metres, label, tag matcher)
# Selectors are kept intentionally light (points/small ways, bounded radii) so a single
# combined query returns quickly; broad polygon scans (e.g. every lake) are avoided.
_POI_SPECS: dict[str, tuple[list[str], int, str, Any]] = {
    "nearest_amtrak": (['nwr["railway"="station"]'], 45000, "train station", lambda t: t.get("railway") == "station"),
    "nearest_airport": (['nwr["aeroway"="aerodrome"]'], 80000, "airport", lambda t: t.get("aeroway") == "aerodrome"),
    "restaurant_hub": (['node["amenity"="restaurant"]'], 6000, "restaurant", lambda t: t.get("amenity") == "restaurant"),
    "grocery_distance": (['nwr["shop"="supermarket"]'], 10000, "grocery store", lambda t: t.get("shop") == "supermarket"),
    "hospital_distance": (['nwr["amenity"="hospital"]'], 30000, "hospital", lambda t: t.get("amenity") == "hospital"),
    "pharmacy_distance": (['node["amenity"="pharmacy"]'], 12000, "pharmacy", lambda t: t.get("amenity") == "pharmacy"),
    "hardware_distance": (['nwr["shop"~"^(hardware|doityourself)$"]'], 20000, "hardware store", lambda t: t.get("shop") in ("hardware", "doityourself")),
    "ski_access": (['nwr["landuse"="winter_sports"]'], 70000, "ski area", lambda t: t.get("landuse") == "winter_sports"),
    "water_access": (['nwr["leisure"="marina"]', 'node["natural"="beach"]', 'nwr["natural"="beach"]'], 25000, "beach / marina access", lambda t: t.get("leisure") == "marina" or t.get("natural") == "beach"),
    "nearest_school": (['nwr["amenity"="school"]'], 15000, "school", lambda t: t.get("amenity") == "school"),
}


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.7613
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlam / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(a))


def _fetch_json(url: str, timeout: float, data: str | None = None, attempts: int = 1) -> Any:
    """Dedicated fetch for Overpass/OSRM. Bounded latency: a single attempt by default
    (mirror rotation is the fallback), never blocking the import on a slow endpoint."""
    request = Request(url, data=data.encode() if data else None,
                      headers={"User-Agent": "Bistate/1.0 (real-estate diligence)", "Accept": "application/json"})
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout) as response:  # nosec B310: public keyless APIs
                return json.loads(response.read().decode())
        except HTTPError as exc:
            if exc.code == 429 and attempt + 1 < attempts:
                time.sleep(1); continue
            raise ProviderError(f"HTTP {exc.code}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 < attempts:
                time.sleep(1); continue
            raise ProviderError("request failed") from exc


def _overpass_around(lat: float, lon: float) -> list[dict[str, Any]]:
    body = "[out:json][timeout:25];(" + "".join(
        f"{selector}(around:{radius},{lat},{lon});"
        for selectors, radius, _, _ in _POI_SPECS.values() for selector in selectors
    ) + ");out center tags;"
    data, last_error = None, None
    for url in OVERPASS_URLS:
        try:
            data = _fetch_json(url, 6, data="data=" + quote(body))
            break
        except ProviderError as exc:
            last_error = exc
    if data is None:
        raise last_error or ProviderError("Overpass unavailable")
    elements: list[dict[str, Any]] = []
    for element in data.get("elements", []):
        centre = element.get("center") or element
        if centre.get("lat") is not None and centre.get("lon") is not None:
            elements.append({"lat": centre["lat"], "lon": centre["lon"], "tags": element.get("tags", {})})
    return elements


def _osrm_table(lat: float, lon: float, destinations: list[tuple[float, float]]) -> tuple[list[Any], list[Any]]:
    coords = ";".join(f"{lo},{la}" for la, lo in [(lat, lon)] + destinations)
    data = _fetch_json(f"{OSRM_URL}/{coords}?sources=0&annotations=duration,distance", 8)
    if data.get("code") != "Ok":
        raise ProviderError(f"OSRM returned {data.get('code', 'no result')}")
    durations = (data.get("durations") or [[None]])[0][1:]
    distances = (data.get("distances") or [[None]])[0][1:]
    return durations, distances


def _compute_access(prop: Property) -> dict[str, Any]:
    """One Overpass query + one OSRM table call → all access facts for the property."""
    lat, lon = prop.latitude, prop.longitude
    elements = _overpass_around(lat, lon)
    nearest: dict[str, dict[str, Any]] = {}
    for key, (_selectors, radius_m, label, matches) in _POI_SPECS.items():
        best, best_dist = None, None
        radius_mi = radius_m / 1609.344
        for element in elements:
            if not matches(element["tags"]):
                continue
            dist = _haversine_miles(lat, lon, element["lat"], element["lon"])
            if dist <= radius_mi and (best_dist is None or dist < best_dist):
                best, best_dist = element, dist
        if best is not None:
            nearest[key] = {"name": best["tags"].get("name") or label.title(), "category": label,
                            "latitude": best["lat"], "longitude": best["lon"], "straight_line_miles": round(best_dist, 1)}

    result: dict[str, Any] = {}
    dest_keys = list(nearest.keys())
    destinations = [(nearest[k]["latitude"], nearest[k]["longitude"]) for k in dest_keys] + [NYC_LATLON]
    try:
        durations, distances = _osrm_table(lat, lon, destinations)
        for index, key in enumerate(dest_keys):
            value = dict(nearest[key])
            value["drive_time_minutes"] = round(durations[index] / 60) if durations[index] is not None else None
            if distances[index] is not None:
                value["road_miles"] = round(distances[index] / 1609.344, 1)
            result[key] = value
        nyc_minutes = round(durations[-1] / 60) if durations[-1] is not None else None
        result["nyc_drive_time"] = {"destination": "Midtown Manhattan", "drive_time_minutes": nyc_minutes,
                                    "straight_line_miles": round(_haversine_miles(lat, lon, *NYC_LATLON), 1),
                                    "road_miles": round(distances[-1] / 1609.344, 1) if distances[-1] is not None else None}
    except ProviderError:
        # Routing degraded: keep the located POIs with straight-line distance only.
        for key in dest_keys:
            value = dict(nearest[key]); value["drive_time_minutes"] = None; value["drive_time_reason"] = "Public router (OSRM) unavailable"
            result[key] = value
        result["nyc_drive_time"] = {"destination": "Midtown Manhattan", "drive_time_minutes": None,
                                    "straight_line_miles": round(_haversine_miles(lat, lon, *NYC_LATLON), 1),
                                    "drive_time_reason": "Public router (OSRM) unavailable"}

    airport = result.get("nearest_airport")
    if airport:
        result["airport_drive_time"] = {"name": airport["name"], "drive_time_minutes": airport.get("drive_time_minutes"),
                                        "road_miles": airport.get("road_miles"), "straight_line_miles": airport.get("straight_line_miles")}
    return result


class OsmAccessProvider:
    """Keyless per-field access provider backed by the shared OSM/OSRM computation."""
    required_setting = None

    def __init__(self, key: str, label: str):
        self.key, self.label, self.source = key, label, OSM_SOURCE

    def fetch(self, prop: Property) -> dict[str, Any]:
        if not get_settings().live_providers_enabled:
            return unavailable("Live public providers are disabled", self.source)
        if prop.latitude is None or prop.longitude is None:
            return unavailable("Coordinates are required; geocode the address first", self.source)
        access = getattr(prop, "_access_facts", None)
        if access is None:
            try:
                access = _compute_access(prop)
            except ProviderError as exc:
                access = {"_error": str(exc)}
            prop._access_facts = access  # type: ignore[attr-defined]
        if access.get("_error"):
            return unavailable(f"OpenStreetMap/OSRM lookup failed: {access['_error']}", self.source)
        value = access.get(self.key)
        if not value:
            return unavailable(f"No {self.label} found nearby in OpenStreetMap", self.source)
        return live(value, self.source, 0.75)


PROVIDERS: list[Provider] = [
    CensusGeocoder(), FemaFloodProvider(), ElevationProvider(), CensusDemographicsProvider(),
    # Keyless, automatic once coordinates exist:
    OsmAccessProvider("nyc_drive_time", "NYC route"),
    OsmAccessProvider("nearest_amtrak", "train station"),
    OsmAccessProvider("nearest_airport", "airport"),
    OsmAccessProvider("airport_drive_time", "airport route"),
    OsmAccessProvider("restaurant_hub", "restaurant"),
    OsmAccessProvider("grocery_distance", "grocery store"),
    OsmAccessProvider("hospital_distance", "hospital"),
    OsmAccessProvider("pharmacy_distance", "pharmacy"),
    OsmAccessProvider("hardware_distance", "hardware store"),
    OsmAccessProvider("ski_access", "ski area"),
    OsmAccessProvider("water_access", "lake / beach / water access"),
    OsmAccessProvider("nearest_school", "school"),
    # Derived Bistate suitability (not external facts):
    SuitabilityProvider("wedding_suitability", _wedding), SuitabilityProvider("airbnb_suitability", _airbnb),
    # Credentialed connectors (honestly unavailable until a key is supplied):
    ConfiguredProvider("county_assessor", "County assessor feed", "assessor_api_key"),
    ConfiguredProvider("parcel_data", "Parcel data provider", "parcel_api_key"),
    ConfiguredProvider("parcel_information", "County parcel provider", "parcel_api_key"),
    ConfiguredProvider("school_ratings", "School ratings provider", "schools_api_key"),
    ZoningProvider(),
    ConfiguredProvider("str_regulations", "STR regulations provider", "str_regulations_api_key"),
    ConfiguredProvider("walkability", "Walkability provider", "walkscore_api_key"),
    ConfiguredProvider("airbnb_intelligence", "STR market-data provider", "airdna_api_key"),
    ConfiguredProvider("wedding_venue", "Property and local-permit diligence", None),
]


def is_stale(item: dict[str, Any], reference: datetime | None = None) -> bool:
    timestamp = item.get("last_updated")
    if not timestamp: return True
    try: updated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError): return True
    # Persisted timestamps can be tz-naive (e.g. SQLite `updated_at`). Treat naive
    # values as UTC so the comparison never mixes offset-naive and offset-aware datetimes.
    if updated.tzinfo is None: updated = updated.replace(tzinfo=timezone.utc)
    return (reference or now()) - updated > STALE_AFTER


def enrich_property(prop: Property, refresh: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    previous, output, errors = prop.enrichment_data or {}, {}, {}
    for provider in PROVIDERS:
        cached = previous.get(provider.key)
        if cached and not refresh and not is_stale(cached): output[provider.key] = cached; continue
        started = time.monotonic()
        try:
            result = provider.fetch(prop)
            # Keep provider provenance even when a connector is intentionally
            # unavailable, so users can distinguish unavailable data from a
            # missing enrichment field.
            if result.get("source") is None:
                result["source"] = provider.source
            output[provider.key] = result
            diagnostic = PROVIDER_DIAGNOSTICS.setdefault(provider.key, {})
            diagnostic["latency_ms"] = round((time.monotonic() - started) * 1000, 1)
            if result.get("value") is not None:
                diagnostic["most_recent_success"] = result.get("last_updated")
        except Exception as exc:
            logger.warning("enrichment_provider_failed", extra={"provider": provider.key, "property_id": prop.id, "error": str(exc)})
            # A transient provider failure must not destroy a previously persisted *live*
            # fact; retain that. But when the prior value was itself unavailable, refresh
            # its reason with the current error instead of pinning a stale message.
            reason = str(exc) if isinstance(exc, ProviderError) else "Provider request failed"
            output[provider.key] = cached if (cached and cached.get("value") is not None) else unavailable(reason, provider.source)
            errors[provider.key] = {"message": str(exc), "at": now().isoformat()}
            PROVIDER_DIAGNOSTICS.setdefault(provider.key, {}).update({"most_recent_failure": errors[provider.key]["at"], "failure_reason": str(exc), "latency_ms": round((time.monotonic() - started) * 1000, 1)})
    return output, errors


def provider_health() -> list[dict[str, Any]]:
    settings = get_settings()
    results = []
    for provider in PROVIDERS:
        configured = provider.required_setting is None or bool(getattr(settings, provider.required_setting, None))
        runtime = PROVIDER_DIAGNOSTICS.get(provider.key, {})
        results.append({
            "provider": provider.key, "source": provider.source,
            "status": "configured" if configured else "unavailable",
            "configured": configured, "enabled": settings.live_providers_enabled,
            "most_recent_success": runtime.get("most_recent_success"),
            "most_recent_failure": runtime.get("most_recent_failure"),
            "latency_ms": runtime.get("latency_ms"),
            "cache_status": "in-memory TTL cache enabled" if settings.provider_cache_seconds > 0 else "disabled",
            "missing_credential_reason": None if configured else f"{provider.required_setting} is not configured",
            "required_setting": provider.required_setting,
        })
    return results
