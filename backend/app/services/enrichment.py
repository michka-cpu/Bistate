"""Resilient, provenance-first live-data provider registry.

Providers deliberately return explicit unavailable records when no approved credentials/feed
is configured; callers never receive inferred market or regulatory facts as live data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.config import get_settings
from app.models.property import Property

STALE_AFTER = timedelta(days=30)


def now() -> datetime: return datetime.now(timezone.utc)


def field(value: Any, source: str, confidence: float = 0.0, missing_reason: str | None = None) -> dict[str, Any]:
    return {"value": value, "source": source, "confidence": confidence, "last_updated": now().isoformat(), "missing_reason": missing_reason}


class Provider(Protocol):
    key: str
    source: str
    required_setting: str | None
    def fetch(self, prop: Property) -> dict[str, Any]: ...


class ConfiguredProvider:
    def __init__(self, key: str, source: str, required_setting: str | None = None):
        self.key, self.source, self.required_setting = key, source, required_setting

    def fetch(self, prop: Property) -> dict[str, Any]:
        # Network integrations are intentionally opt-in. An API key alone is not treated as
        # authorization to scrape a provider or consume a licensed listing/assessor feed.
        configured = bool(getattr(get_settings(), self.required_setting, None)) if self.required_setting else False
        reason = "Provider credentials are not configured" if not configured else "Live connector is not enabled for this provider"
        return field(None, self.source, missing_reason=reason)


PROVIDERS: list[Provider] = [
    ConfiguredProvider("fema_flood", "FEMA National Flood Hazard Layer", "fema_api_url"),
    ConfiguredProvider("census_demographics", "U.S. Census Bureau", "census_api_key"),
    ConfiguredProvider("county_assessor", "County assessor feed", "assessor_api_key"),
    ConfiguredProvider("parcel_data", "Parcel data provider", "parcel_api_key"),
    ConfiguredProvider("school_ratings", "School ratings provider", "schools_api_key"),
    ConfiguredProvider("zoning", "County zoning provider", "zoning_api_key"),
    ConfiguredProvider("str_regulations", "STR regulations provider", "str_regulations_api_key"),
    ConfiguredProvider("nyc_drive_time", "Routing provider", "routing_api_key"),
    ConfiguredProvider("nearest_airport", "Places and routing provider", "places_api_key"),
    ConfiguredProvider("nearest_amtrak", "Places and routing provider", "places_api_key"),
    ConfiguredProvider("hospital_distance", "Places and routing provider", "places_api_key"),
    ConfiguredProvider("grocery_distance", "Places and routing provider", "places_api_key"),
    ConfiguredProvider("walkability", "Walkability provider", "walkscore_api_key"),
    ConfiguredProvider("airbnb_intelligence", "STR market-data provider", "airdna_api_key"),
    ConfiguredProvider("wedding_venue", "Property and local-permit diligence", None),
]


def is_stale(item: dict[str, Any], reference: datetime | None = None) -> bool:
    timestamp = item.get("last_updated")
    if not timestamp: return True
    try: updated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError: return True
    return (reference or now()) - updated > STALE_AFTER


def enrich_property(prop: Property, refresh: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    previous = prop.enrichment_data or {}
    output, errors = dict(previous), {}
    for provider in PROVIDERS:
        cached = previous.get(provider.key)
        if cached and not refresh and not is_stale(cached):
            output[provider.key] = cached
            continue
        try:
            output[provider.key] = provider.fetch(prop)
        except Exception as exc:  # provider isolation preserves all partial results
            output[provider.key] = field(None, provider.source, missing_reason="Provider request failed")
            errors[provider.key] = {"message": str(exc), "at": now().isoformat()}
    return output, errors


def provider_health() -> list[dict[str, Any]]:
    settings = get_settings()
    return [{"provider": p.key, "source": p.source, "status": "configured" if p.required_setting and getattr(settings, p.required_setting, None) else "unavailable", "required_setting": p.required_setting} for p in PROVIDERS]
