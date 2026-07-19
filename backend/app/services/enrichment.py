from datetime import datetime, timezone
from typing import Any, Callable

from app.models.property import Property


def _field(value: Any, source: str, confidence: float) -> dict[str, Any]:
    return {
        "value": value,
        "source": source,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "confidence": confidence,
    }


def _acreage_suitability(prop: Property) -> int | None:
    return min(100, round(45 + prop.acreage * 12)) if prop.acreage is not None else None


def _airbnb_suitability(prop: Property) -> int | None:
    if prop.bedrooms is None:
        return None
    return min(100, round(45 + prop.bedrooms * 7 + (prop.bathrooms or 0) * 4))


ADAPTERS: dict[str, tuple[str, Callable[[Property], Any]]] = {
    "fema_flood": ("FEMA National Flood Hazard Layer", lambda _: None),
    "school_ratings": ("GreatSchools provider", lambda _: None),
    "str_regulations": ("Local municipal code provider", lambda _: None),
    "airport_drive_time": ("Routing provider", lambda _: None),
    "nyc_drive_time": ("Routing provider", lambda _: None),
    "hospital_distance": ("Places and routing provider", lambda _: None),
    "grocery_distance": ("Places and routing provider", lambda _: None),
    "walkability": ("Walkability provider", lambda _: None),
    "wedding_suitability": ("Bistate suitability model", _acreage_suitability),
    "airbnb_suitability": ("Bistate suitability model", _airbnb_suitability),
    "zoning": ("County zoning provider", lambda _: None),
    "parcel_information": ("County parcel provider", lambda _: None),
}


def enrich_property(prop: Property) -> dict[str, dict[str, Any]]:
    result = {}
    for key, (source, resolver) in ADAPTERS.items():
        value = resolver(prop)
        confidence = 0.65 if value is not None else 0.0
        result[key] = _field(value, source, confidence)
    return result
