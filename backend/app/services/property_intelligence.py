"""Read-only due-diligence explainability over persisted facts.

This module does not participate in underwriting. It reshapes the enrichment/listing/
identity facts for the UI and separates three axes of coverage:

- ``auto``   — retrieved automatically from verified coordinates with no API key
- ``keyed``  — retrievable once a (free or paid) credential is configured
- ``manual`` — genuine on-the-ground diligence with no automated source

Data Completeness reports the *automatic* axis, so verified facts Bistate already holds
(address, coordinates, county, elevation, flood, nearby amenities) are counted rather
than ignored; keyed and manual coverage are tracked separately.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.property import Property
from app.schemas.property import property_listing_incomplete
from app.services.enrichment import is_stale

# Every displayed field maps to a real provider/derived fact (auto), a credentialed
# connector (keyed), or an explicit manual-diligence item (manual).
SECTIONS: dict[str, list[tuple[str, str, str]]] = {
    "Location & identity": [
        ("resolved_address", "Verified address", "auto"),
        ("coordinates", "Coordinates", "auto"),
        ("county", "County", "auto"),
        ("census_tract", "Census tract", "auto"),
        ("elevation", "Elevation", "auto"),
    ],
    "Access & amenities": [
        ("nyc_drive_time", "NYC driving time", "auto"),
        ("nearest_amtrak", "Nearest train station", "auto"),
        ("nearest_airport", "Nearest airport", "auto"),
        ("restaurant_hub", "Restaurants nearby", "auto"),
        ("grocery_distance", "Grocery", "auto"),
        ("hospital_distance", "Hospital", "auto"),
        ("pharmacy_distance", "Pharmacy", "auto"),
        ("hardware_distance", "Hardware store", "auto"),
        ("ski_access", "Ski access", "auto"),
        ("water_access", "Lake / beach access", "auto"),
        ("nearest_school", "Nearest school", "auto"),
    ],
    "Environment": [
        ("fema_flood", "Flood zone (FEMA)", "auto"),
        ("wetlands", "Wetlands", "manual"),
        ("slopes", "Steep slopes", "manual"),
        ("protected_land", "Protected / conservation land", "manual"),
    ],
    "Property & parcel": [
        ("confirmed_acreage", "Lot size / acreage", "auto"),
        ("current_taxes", "Property taxes", "auto"),
        ("hoa", "HOA", "auto"),
        ("parcel_information", "Parcel details", "keyed"),
        ("assessment_history", "Assessment history", "manual"),
    ],
    "Regulatory": [
        ("zoning", "Zoning", "keyed"),
        ("str_regulations", "STR rules", "keyed"),
        ("event_restrictions", "Wedding / event restrictions", "manual"),
        ("permits", "Permits requiring review", "manual"),
    ],
    "Demographics & schools": [
        ("census_demographics", "Area demographics (ACS)", "keyed"),
        ("school_ratings", "School ratings", "keyed"),
    ],
    "Utilities & infrastructure": [
        ("water", "Water source", "manual"),
        ("septic", "Sewer / septic", "manual"),
        ("electricity", "Electricity", "manual"),
        ("internet", "Internet / broadband", "manual"),
    ],
}


def _missing(key: str, label: str, kind: str) -> dict[str, Any]:
    reason = {
        "auto": "Not yet retrieved automatically; refresh intelligence to retry.",
        "keyed": "Available once the provider credential is configured.",
        "manual": "No automated source; verify during on-the-ground diligence.",
    }[kind]
    status = {"auto": "Needs manual review", "keyed": "Provider not configured", "manual": "Needs manual review"}[kind]
    return {"key": key, "label": label, "kind": kind, "value": None, "source": None, "retrieval_status": "manual_review", "display_status": status, "confidence": 0, "last_updated": None, "missing_reason": reason}


def _field(key: str, label: str, kind: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    item = {**_missing(key, label, kind), **(raw or {}), "key": key, "label": label, "kind": kind}
    reason = str(item.get("missing_reason") or "").lower()
    if raw and is_stale(raw) and raw.get("last_updated"):
        item["display_status"] = "Stale"
    elif item.get("value") is not None:
        item["display_status"] = "Verified" if float(item.get("confidence") or 0) >= .9 else "Available"
    elif "credential" in reason or kind == "keyed":
        item["display_status"] = "Provider not configured"
    elif item.get("retrieval_status") == "unavailable":
        item["display_status"] = "Unavailable"
    return item


def _stored(value: Any, source: str, updated: datetime, confidence: float = .7) -> dict[str, Any]:
    return {"value": value, "source": source, "retrieval_status": "stored", "confidence": confidence, "last_updated": updated.isoformat(), "missing_reason": None}


def _fact_source(prop: Property, field: str) -> str:
    """Provenance for a column-backed fact: the listing (with provider) or a stored record."""
    item = (prop.listing_data or {}).get(field) or {}
    if item.get("value") is not None and item.get("source"):
        return f"Listing ({item['source']})"
    return "Stored property record"


def build_property_intelligence(prop: Property) -> dict[str, Any]:
    facts = dict(prop.enrichment_data or {})
    updated = prop.updated_at or datetime.now(timezone.utc)

    # Surface verified identity facts Bistate already holds (columns + geocoding).
    if not property_listing_incomplete(prop):
        facts.setdefault("resolved_address", _stored(", ".join(filter(None, [prop.address, prop.city, prop.state, prop.postal_code])), "Verified address", updated, .95))
    if prop.latitude is not None and prop.longitude is not None:
        facts.setdefault("coordinates", _stored({"latitude": round(prop.latitude, 5), "longitude": round(prop.longitude, 5)}, "U.S. Census Geocoder", updated, .95))
    if prop.county:
        facts.setdefault("county", _stored(prop.county, (facts.get("geocoding") or {}).get("source") or "U.S. Census Geocoder", updated, .9))
    geo_value = (facts.get("geocoding") or {}).get("value") or {}
    if geo_value.get("census_tract"):
        facts.setdefault("census_tract", _stored(geo_value["census_tract"], "U.S. Census Geocoder", updated, .9))

    # Listing/user-derived property facts (kept distinct from enrichment).
    if prop.acreage is not None:
        facts.setdefault("confirmed_acreage", _stored(prop.acreage, _fact_source(prop, "acreage"), updated))
    if prop.annual_taxes is not None:
        facts.setdefault("current_taxes", _stored(prop.annual_taxes, _fact_source(prop, "annual_taxes"), updated))
    if prop.hoa is not None:
        facts.setdefault("hoa", _stored(prop.hoa, _fact_source(prop, "hoa"), updated))

    sections = [{"name": name, "fields": [_field(key, label, kind, facts.get(key)) for key, label, kind in definitions]} for name, definitions in SECTIONS.items()]
    fields = [field for section in sections for field in section["fields"]]
    flags = derive_red_flags(prop, facts)
    opportunities = derive_opportunities(prop, facts)

    auto = [f for f in fields if f["kind"] == "auto"]
    keyed = [f for f in fields if f["kind"] == "keyed"]
    manual = [f for f in fields if f["kind"] == "manual"]
    auto_covered = [f for f in auto if f.get("value") is not None]
    keyed_covered = [f for f in keyed if f.get("value") is not None]
    checked = {f["source"] for f in fields if f.get("source") and f.get("value") is not None}

    completeness = {
        # Headline = automatic (keyless) coverage, so verified facts are counted.
        "percentage_complete": round(len(auto_covered) / max(1, len(auto)) * 100),
        "auto_fields_total": len(auto),
        "auto_fields_covered": len(auto_covered),
        "keyed_fields_total": len(keyed),
        "keyed_fields_available": len(keyed_covered),
        "manual_diligence_remaining": len(manual),
        "verified_fields": sum(f["display_status"] in {"Verified", "Available"} for f in fields),
        "unavailable_fields": sum(f["display_status"] in {"Unavailable", "Provider not configured"} for f in fields),
        "providers_checked": len(checked),
        "stale_fields": sum(f["display_status"] == "Stale" for f in fields),
        "manual_reviews_required": len(manual),
        "method": "Data Completeness is automatic (keyless) coverage: facts retrieved from verified coordinates divided by keyless facts attempted. Credentialed and manual-diligence fields are tracked separately and never affect acquisition scores.",
    }
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "sections": sections, "red_flags": flags, "opportunities": opportunities, "completeness": completeness}


def _flag(severity: str, basis: str, uses: list[str], sources: list[str], action: str) -> dict[str, Any]:
    return {"severity": severity, "factual_basis": basis, "affected_use_cases": uses, "source_fields": sources, "recommended_action": action}


def derive_red_flags(prop: Property, facts: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    flood = (facts.get("fema_flood") or {}).get("value") or {}
    if flood.get("flood_risk") == "special_flood_hazard_area" or flood.get("flood_zone") in {"A", "AE", "AH", "AO", "V", "VE"}:
        flags.append(_flag("High", f"FEMA data reports flood zone {flood.get('flood_zone') or 'with special flood hazard exposure'}.", ["Personal second home", "Whole-house Airbnb", "Wedding/private event"], ["fema_flood"], "Obtain an elevation certificate, insurance quote, and floodplain review."))
    nyc = ((facts.get("nyc_drive_time") or {}).get("value") or {}).get("drive_time_minutes")
    if isinstance(nyc, (int, float)) and nyc > 180:
        flags.append(_flag("Medium", f"Estimated driving time to NYC is {nyc} minutes.", ["Personal second home", "Whole-house Airbnb"], ["nyc_drive_time"], "Validate peak and weekend travel times."))
    taxes = prop.annual_taxes
    if taxes and prop.asking_price and taxes / prop.asking_price > .03:
        flags.append(_flag("Medium", f"Annual taxes are {taxes / prop.asking_price:.1%} of asking price.", ["Personal second home", "Whole-house Airbnb", "Wedding/private event"], ["current_taxes"], "Confirm the tax bill, reassessment basis, and exemptions with the assessor."))
    for key, basis, uses, action in [("parcel_information", "Parcel information is not established.", ["Wedding/private event"], "Obtain the deed, survey, parcel card, and easements."), ("zoning", "Zoning compatibility is not established.", ["Whole-house Airbnb", "Wedding/private event"], "Request a written zoning determination."), ("str_regulations", "STR rules are not established.", ["Whole-house Airbnb"], "Confirm permits, caps, occupancy, and owner-presence rules."), ("event_restrictions", "Wedding and event restrictions are not established.", ["Wedding/private event"], "Confirm event, assembly, parking, fire, noise, and liquor requirements."), ("water", "Water source / well condition is uncertain.", ["Personal second home", "Whole-house Airbnb", "Wedding/private event"], "Order potability, yield, and equipment testing."), ("septic", "Sewer / septic capacity is uncertain.", ["Whole-house Airbnb", "Wedding/private event"], "Obtain design, inspection, pumping, and permitted-capacity records."), ("internet", "Internet service availability is unknown.", ["Personal second home", "Whole-house Airbnb"], "Request address-level provider availability and speed evidence.")]:
        if (facts.get(key) or {}).get("value") is None:
            flags.append(_flag("Medium" if key in {"zoning", "str_regulations", "event_restrictions", "septic"} else "Low", basis, uses, [key], action))
    return flags


def derive_opportunities(prop: Property, facts: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    def add(title: str, basis: str, uses: list[str], sources: list[str]) -> None:
        items.append({"title": title, "factual_basis": basis, "affected_use_cases": uses, "source_fields": sources})
    nyc = ((facts.get("nyc_drive_time") or {}).get("value") or {}).get("drive_time_minutes")
    if isinstance(nyc, (int, float)) and nyc <= 150:
        add("Strong NYC access", f"Estimated driving time is {nyc} minutes.", ["Personal second home", "Whole-house Airbnb"], ["nyc_drive_time"])
    train = (facts.get("nearest_amtrak") or {}).get("value") or {}
    if train.get("name"):
        add("Nearby train service", f"OpenStreetMap places {train['name']} about {train.get('straight_line_miles', '?')} mi away.", ["Personal second home", "Whole-house Airbnb", "Wedding/private event"], ["nearest_amtrak"])
    restaurant = (facts.get("restaurant_hub") or {}).get("value") or {}
    if restaurant.get("name"):
        add("Restaurant-town proximity", f"OpenStreetMap places {restaurant['name']} nearby.", ["Personal second home", "Whole-house Airbnb"], ["restaurant_hub"])
    ski = (facts.get("ski_access") or {}).get("value") or {}
    if ski.get("name") and isinstance(ski.get("drive_time_minutes"), (int, float)) and ski["drive_time_minutes"] <= 45:
        add("Ski-area access", f"{ski['name']} is about {ski['drive_time_minutes']} minutes away.", ["Whole-house Airbnb", "Personal second home"], ["ski_access"])
    if prop.acreage is not None and prop.acreage >= 5:
        add("Land-based diligence potential", f"The stored property record reports {prop.acreage:g} acres.", ["Wedding/private event"], ["confirmed_acreage"])
    str_value = (facts.get("str_regulations") or {}).get("value")
    if isinstance(str_value, dict) and str_value.get("status") in {"allowed", "permitted"}:
        add("Favorable STR status", f"Stored STR status is {str_value['status']}.", ["Whole-house Airbnb"], ["str_regulations"])
    return items
