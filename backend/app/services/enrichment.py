"""Production-safe public-data enrichment adapters with a stable API contract."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import get_settings
from app.models.property import Property

logger = logging.getLogger(__name__)
STALE_AFTER = timedelta(days=30)
NYC_ORIGIN = "21 W 38th St, New York, NY"


def now() -> datetime: return datetime.now(timezone.utc)


def unavailable(reason: str) -> dict[str, Any]:
    return {"value": None, "source": None, "confidence": 0, "last_updated": None, "missing_reason": reason}


def live(value: Any, source: str, confidence: float = 0.9) -> dict[str, Any]:
    return {"value": value, "source": source, "confidence": confidence, "last_updated": now().isoformat(), "missing_reason": None}


class ProviderError(Exception): pass
class RateLimitError(ProviderError): pass


class JsonHttpClient:
    """Small, dependency-free HTTP client with bounded retries and rate-limit handling."""
    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        settings = get_settings()
        url = f"{url}?{urlencode(params, doseq=True)}" if params else url
        for attempt in range(settings.provider_retry_count + 1):
            try:
                request = Request(url, headers={"Accept": "application/json", "User-Agent": "Bistate/1.0"})
                with urlopen(request, timeout=settings.provider_timeout_seconds) as response:  # nosec B310: configured public APIs
                    return json.loads(response.read().decode())
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


class Provider(Protocol):
    key: str
    source: str
    required_setting: str | None
    def fetch(self, prop: Property) -> dict[str, Any]: ...


class CensusGeocoder:
    key, source, required_setting = "geocoding", "U.S. Census Geocoder", None
    def fetch(self, prop: Property) -> dict[str, Any]:
        if not get_settings().live_providers_enabled: return unavailable("Live public providers are disabled")
        address = ", ".join(filter(None, [prop.address, prop.city, prop.state, prop.postal_code]))
        data = HTTP.get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress", {"address": address, "benchmark": "Public_AR_Current", "format": "json"})
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches: return unavailable("Address was not matched by the U.S. Census Geocoder")
        coordinates = matches[0].get("coordinates", {})
        if not {"x", "y"} <= coordinates.keys(): return unavailable("Geocoder response did not include coordinates")
        prop.longitude, prop.latitude = coordinates["x"], coordinates["y"]
        return live({"latitude": prop.latitude, "longitude": prop.longitude, "geographies": matches[0].get("addressComponents", {})}, self.source, 0.95)


class FemaFloodProvider:
    key, source, required_setting = "fema_flood", "FEMA National Flood Hazard Layer", None
    url = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
    def fetch(self, prop: Property) -> dict[str, Any]:
        if not get_settings().live_providers_enabled: return unavailable("Live public providers are disabled")
        if prop.latitude is None or prop.longitude is None: return unavailable("Latitude and longitude are required for FEMA flood lookup")
        point = f"{prop.longitude},{prop.latitude}"
        data = HTTP.get(self.url, {"geometry": point, "geometryType": "esriGeometryPoint", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "FLD_ZONE,FLD_ZONE_SUBTY,SFHA_TF", "returnGeometry": "false", "f": "json"})
        features = data.get("features")
        if not isinstance(features, list): return unavailable("Malformed FEMA flood response")
        if not features: return live({"flood_zone": None, "flood_risk": "outside_mapped_special_flood_hazard_area", "map_panel": None}, self.source, 0.8)
        attrs = features[0].get("attributes", {})
        zone = attrs.get("FLD_ZONE")
        return live({"flood_zone": zone, "flood_risk": "special_flood_hazard_area" if attrs.get("SFHA_TF") == "T" else "mapped", "map_panel": attrs.get("FLD_ZONE_SUBTY")}, self.source, 0.9)


class CensusDemographicsProvider:
    key, source, required_setting = "census_demographics", "U.S. Census Bureau ACS 5-Year API", None
    def fetch(self, prop: Property) -> dict[str, Any]:
        if not get_settings().live_providers_enabled: return unavailable("Live public providers are disabled")
        if prop.latitude is None or prop.longitude is None: return unavailable("Latitude and longitude are required for Census geography lookup")
        geo = HTTP.get("https://geocoding.geo.census.gov/geocoder/geographies/coordinates", {"x": prop.longitude, "y": prop.latitude, "benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"})
        geos = geo.get("result", {}).get("geographies", {})
        tract = (geos.get("Census Tracts") or [{}])[0]
        state, county, tract_code = tract.get("STATE"), tract.get("COUNTY"), tract.get("TRACT")
        if not all((state, county, tract_code)): return unavailable("Census tract was not available for coordinates")
        variables = "NAME,B01003_001E,B19013_001E,B01002_001E,B25002_001E,B25003_002E,B25003_003E"
        rows = HTTP.get("https://api.census.gov/data/2023/acs/acs5", {"get": variables, "for": f"tract:{tract_code}", "in": [f"state:{state}", f"county:{county}"]})
        if not isinstance(rows, list) or len(rows) < 2: return unavailable("Census ACS response contained no tract data")
        headers, values = rows[0], rows[1]; record = dict(zip(headers, values))
        def number(key: str) -> int | None:
            try: return int(record[key])
            except (KeyError, TypeError, ValueError): return None
        occupied, owner, renter = number("B25002_001E"), number("B25003_002E"), number("B25003_003E")
        return live({"geography": {"state": state, "county": county, "tract": tract_code}, "population": number("B01003_001E"), "median_household_income": number("B19013_001E"), "median_age": number("B01002_001E"), "housing_occupancy": occupied, "owner_occupied": owner, "renter_occupied": renter}, self.source, 0.9)


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

PROVIDERS: list[Provider] = [CensusGeocoder(), FemaFloodProvider(), CensusDemographicsProvider(), ConfiguredProvider("county_assessor", "County assessor feed", "assessor_api_key"), ConfiguredProvider("parcel_data", "Parcel data provider", "parcel_api_key"), ConfiguredProvider("parcel_information", "County parcel provider", "parcel_api_key"), ConfiguredProvider("school_ratings", "School ratings provider", "schools_api_key"), ConfiguredProvider("zoning", "County zoning provider", "zoning_api_key"), ConfiguredProvider("str_regulations", "STR regulations provider", "str_regulations_api_key"), ConfiguredProvider("nyc_drive_time", "Routing provider", "routing_api_key"), ConfiguredProvider("airport_drive_time", "Routing provider", "routing_api_key"), ConfiguredProvider("nearest_airport", "Places and routing provider", "places_api_key"), ConfiguredProvider("nearest_amtrak", "Places and routing provider", "places_api_key"), ConfiguredProvider("hospital_distance", "Places and routing provider", "places_api_key"), ConfiguredProvider("grocery_distance", "Places and routing provider", "places_api_key"), ConfiguredProvider("walkability", "Walkability provider", "walkscore_api_key"), SuitabilityProvider("wedding_suitability", _wedding), SuitabilityProvider("airbnb_suitability", _airbnb), ConfiguredProvider("airbnb_intelligence", "STR market-data provider", "airdna_api_key"), ConfiguredProvider("wedding_venue", "Property and local-permit diligence", None)]


def is_stale(item: dict[str, Any], reference: datetime | None = None) -> bool:
    timestamp = item.get("last_updated")
    if not timestamp: return True
    try: updated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError: return True
    return (reference or now()) - updated > STALE_AFTER


def enrich_property(prop: Property, refresh: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    previous, output, errors = prop.enrichment_data or {}, {}, {}
    for provider in PROVIDERS:
        cached = previous.get(provider.key)
        if cached and not refresh and not is_stale(cached): output[provider.key] = cached; continue
        try: output[provider.key] = provider.fetch(prop)
        except Exception as exc:
            logger.warning("enrichment_provider_failed", extra={"provider": provider.key, "property_id": prop.id, "error": str(exc)})
            output[provider.key] = unavailable(str(exc) if isinstance(exc, ProviderError) else "Provider request failed")
            errors[provider.key] = {"message": str(exc), "at": now().isoformat()}
    return output, errors


def provider_health() -> list[dict[str, Any]]:
    settings = get_settings()
    return [{"provider": p.key, "source": p.source, "status": "configured" if (p.required_setting is None and settings.live_providers_enabled) or (p.required_setting and getattr(settings, p.required_setting, None)) else "unavailable", "required_setting": p.required_setting} for p in PROVIDERS]
