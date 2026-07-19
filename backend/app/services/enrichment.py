"""Resilient, provenance-first live-data provider registry.

The legacy enrichment keys remain part of the public acquisition contract. Every run
returns every key, even when an adapter is unavailable or has failed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.config import get_settings
from app.models.property import Property

STALE_AFTER = timedelta(days=30)


def now() -> datetime:
    return datetime.now(timezone.utc)


def unavailable(missing_reason: str) -> dict[str, Any]:
    """The canonical shape for a provider without a usable live result."""
    return {
        "value": None,
        "source": None,
        "confidence": 0,
        "last_updated": None,
        "missing_reason": missing_reason,
    }


def result(value: Any, source: str, confidence: float) -> dict[str, Any]:
    return {
        "value": value,
        "source": source,
        "confidence": confidence,
        "last_updated": now().isoformat(),
        "missing_reason": None,
    }


class Provider(Protocol):
    key: str
    source: str
    required_setting: str | None

    def fetch(self, prop: Property) -> dict[str, Any]: ...


class ConfiguredProvider:
    def __init__(self, key: str, source: str, required_setting: str | None = None):
        self.key, self.source, self.required_setting = key, source, required_setting

    def fetch(self, prop: Property) -> dict[str, Any]:
        configured = bool(getattr(get_settings(), self.required_setting, None)) if self.required_setting else False
        if not configured:
            return unavailable("Provider credentials are not configured")
        # An environment variable does not authorize scraping or imply a licensed feed.
        return unavailable("Live connector is not enabled for this provider")


class SuitabilityProvider:
    """Preserves PR #5's transparent, property-fact suitability contract."""

    required_setting = None

    def __init__(self, key: str, source: str, resolver):
        self.key, self.source, self.resolver = key, source, resolver

    def fetch(self, prop: Property) -> dict[str, Any]:
        value = self.resolver(prop)
        return unavailable("Required property facts are unavailable") if value is None else result(value, self.source, 0.65)


def _wedding_suitability(prop: Property) -> int | None:
    return min(100, round(45 + prop.acreage * 12)) if prop.acreage is not None else None


def _airbnb_suitability(prop: Property) -> int | None:
    if prop.bedrooms is None:
        return None
    return min(100, round(45 + prop.bedrooms * 7 + (prop.bathrooms or 0) * 4))


# Keep these legacy aliases indefinitely; dashboard, underwriting, and API clients use them.
PROVIDERS: list[Provider] = [
    ConfiguredProvider("fema_flood", "FEMA National Flood Hazard Layer", "fema_api_url"),
    ConfiguredProvider("census_demographics", "U.S. Census Bureau", "census_api_key"),
    ConfiguredProvider("county_assessor", "County assessor feed", "assessor_api_key"),
    ConfiguredProvider("parcel_data", "Parcel data provider", "parcel_api_key"),
    ConfiguredProvider("parcel_information", "County parcel provider", "parcel_api_key"),
    ConfiguredProvider("school_ratings", "School ratings provider", "schools_api_key"),
    ConfiguredProvider("zoning", "County zoning provider", "zoning_api_key"),
    ConfiguredProvider("str_regulations", "STR regulations provider", "str_regulations_api_key"),
    ConfiguredProvider("nyc_drive_time", "Routing provider", "routing_api_key"),
    ConfiguredProvider("airport_drive_time", "Routing provider", "routing_api_key"),
    ConfiguredProvider("nearest_airport", "Places and routing provider", "places_api_key"),
    ConfiguredProvider("nearest_amtrak", "Places and routing provider", "places_api_key"),
    ConfiguredProvider("hospital_distance", "Places and routing provider", "places_api_key"),
    ConfiguredProvider("grocery_distance", "Places and routing provider", "places_api_key"),
    ConfiguredProvider("walkability", "Walkability provider", "walkscore_api_key"),
    SuitabilityProvider("wedding_suitability", "Bistate suitability model", _wedding_suitability),
    SuitabilityProvider("airbnb_suitability", "Bistate suitability model", _airbnb_suitability),
    ConfiguredProvider("airbnb_intelligence", "STR market-data provider", "airdna_api_key"),
    ConfiguredProvider("wedding_venue", "Property and local-permit diligence"),
]


def is_stale(item: dict[str, Any], reference: datetime | None = None) -> bool:
    timestamp = item.get("last_updated")
    if not timestamp:
        return True
    try:
        updated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return True
    return (reference or now()) - updated > STALE_AFTER


def enrich_property(prop: Property, refresh: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    previous = prop.enrichment_data or {}
    output: dict[str, dict[str, Any]] = {}
    errors: dict[str, dict[str, str]] = {}
    for provider in PROVIDERS:
        cached = previous.get(provider.key)
        if cached and not refresh and not is_stale(cached):
            output[provider.key] = cached
            continue
        try:
            output[provider.key] = provider.fetch(prop)
        except Exception as exc:  # one bad provider must not discard any other result
            output[provider.key] = unavailable("Provider request failed")
            errors[provider.key] = {"message": str(exc), "at": now().isoformat()}
    return output, errors


def provider_health() -> list[dict[str, Any]]:
    settings = get_settings()
    return [
        {
            "provider": p.key,
            "source": p.source,
            "status": "configured" if p.required_setting and getattr(settings, p.required_setting, None) else "unavailable",
            "required_setting": p.required_setting,
        }
        for p in PROVIDERS
    ]
