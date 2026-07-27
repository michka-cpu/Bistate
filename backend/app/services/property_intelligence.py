"""Read-only due-diligence explainability over persisted enrichment facts.

This module deliberately does not participate in underwriting.  It reshapes the
existing provider contract for the UI and derives factual prompts for diligence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.property import Property
from app.services.enrichment import PROVIDERS, is_stale


SECTIONS: dict[str, list[tuple[str, str]]] = {
    "Access": [("nyc_drive_time", "NYC driving time"), ("nearest_amtrak", "Nearest train station"), ("nearest_airport", "Airport"), ("restaurant_hub", "Restaurant hub"), ("grocery_distance", "Grocery"), ("hospital_distance", "Hospital"), ("pharmacy_distance", "Pharmacy"), ("hardware_distance", "Hardware store"), ("ski_access", "Ski access"), ("water_access", "Lake / beach access")],
    "Land and environment": [("confirmed_acreage", "Confirmed acreage"), ("parcel_information", "Parcel details"), ("fema_flood", "Flood zone and FEMA risk"), ("wetlands", "Wetlands"), ("slopes", "Slopes"), ("protected_land", "Protected land"), ("conservation_restrictions", "Conservation restrictions"), ("expansion_potential", "Expansion potential")],
    "Infrastructure": [("water", "Public water"), ("well", "Well"), ("sewer", "Sewer"), ("septic", "Septic"), ("electricity", "Electricity"), ("natural_gas", "Natural gas"), ("internet", "Internet"), ("fiber", "Fiber"), ("utility_providers", "Utility providers")],
    "Regulatory": [("zoning", "Zoning"), ("str_regulations", "STR rules"), ("event_restrictions", "Wedding / event restrictions"), ("occupancy_noise", "Occupancy / noise restrictions"), ("hoa", "HOA"), ("historic_district", "Historic district"), ("permits", "Permits requiring review")],
    "Financial and civic": [("current_taxes", "Current taxes"), ("tax_history", "Tax history"), ("assessment_history", "Assessment history"), ("exemptions", "Exemptions"), ("school_district", "School district"), ("carrying_cost_inputs", "Carrying-cost inputs")],
}


def _missing(key: str, label: str) -> dict[str, Any]:
    return {"key": key, "label": label, "value": None, "source": None, "retrieval_status": "manual_review", "display_status": "Needs manual review", "confidence": 0, "last_updated": None, "missing_reason": "No stored fact is available; verify during diligence."}


def _field(key: str, label: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    item = {**_missing(key, label), **(raw or {}), "key": key, "label": label}
    reason = str(item.get("missing_reason") or "").lower()
    if raw and is_stale(raw) and raw.get("last_updated"):
        item["display_status"] = "Stale"
    elif item.get("value") is not None:
        item["display_status"] = "Verified" if float(item.get("confidence") or 0) >= .9 else "Available"
    elif "credential" in reason:
        item["display_status"] = "Provider not configured"
    elif item.get("retrieval_status") == "unavailable":
        item["display_status"] = "Unavailable"
    return item


def _stored(value: Any, source: str, updated: datetime, confidence: float = .7) -> dict[str, Any]:
    return {"value": value, "source": source, "retrieval_status": "stored", "confidence": confidence, "last_updated": updated.isoformat(), "missing_reason": None}


def build_property_intelligence(prop: Property) -> dict[str, Any]:
    facts = dict(prop.enrichment_data or {})
    updated = prop.updated_at or datetime.now(timezone.utc)
    if prop.acreage is not None: facts.setdefault("confirmed_acreage", _stored(prop.acreage, prop.listing_source or "Stored property record", updated))
    if prop.annual_taxes is not None: facts.setdefault("current_taxes", _stored(prop.annual_taxes, prop.listing_source or "Stored property record", updated))
    if prop.hoa is not None: facts.setdefault("hoa", _stored(prop.hoa, prop.listing_source or "Stored property record", updated))
    facts.setdefault("carrying_cost_inputs", _stored({"annual_taxes": prop.annual_taxes, "hoa": prop.hoa}, "Stored underwriting inputs", updated, .65) if prop.annual_taxes is not None or prop.hoa is not None else None)
    sections = [{"name": name, "fields": [_field(key, label, facts.get(key)) for key, label in definitions]} for name, definitions in SECTIONS.items()]
    fields = [field for section in sections for field in section["fields"]]
    flags = derive_red_flags(prop, facts)
    opportunities = derive_opportunities(prop, facts)
    checked = {field["source"] for field in fields if field.get("source")}
    available = [f for f in fields if f.get("value") is not None]
    completeness = {
        "percentage_complete": round(len(available) / len(fields) * 100),
        "verified_fields": sum(f["display_status"] == "Verified" for f in fields),
        "unavailable_fields": sum(f["display_status"] in {"Unavailable", "Provider not configured"} for f in fields),
        "providers_checked": len(checked),
        "stale_fields": sum(f["display_status"] == "Stale" for f in fields),
        "manual_reviews_required": sum(f["display_status"] == "Needs manual review" for f in fields),
        "method": "Populated fields divided by all displayed intelligence fields; this measures coverage only and never affects acquisition scores.",
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
    if isinstance(nyc, (int, float)) and nyc > 180: flags.append(_flag("Medium", f"Stored route duration to NYC is {nyc} minutes.", ["Personal second home", "Whole-house Airbnb"], ["nyc_drive_time"], "Validate peak and weekend travel times."))
    taxes = prop.annual_taxes
    if taxes and prop.asking_price and taxes / prop.asking_price > .03: flags.append(_flag("Medium", f"Annual taxes are {taxes / prop.asking_price:.1%} of asking price.", ["Personal second home", "Whole-house Airbnb", "Wedding/private event"], ["current_taxes"], "Confirm the tax bill, reassessment basis, and exemptions with the assessor."))
    for key, basis, uses, action in [("parcel_information", "Parcel information is missing.", ["Wedding/private event"], "Obtain the deed, survey, parcel card, and easements."), ("zoning", "Zoning compatibility is not established.", ["Whole-house Airbnb", "Wedding/private event"], "Request a written zoning determination."), ("str_regulations", "STR rules are not established.", ["Whole-house Airbnb"], "Confirm permits, caps, occupancy, and owner-presence rules."), ("event_restrictions", "Wedding and event restrictions are not established.", ["Wedding/private event"], "Confirm event, assembly, parking, fire, noise, and liquor requirements."), ("well", "Water source / well condition is uncertain.", ["Personal second home", "Whole-house Airbnb", "Wedding/private event"], "Order potability, yield, and equipment testing."), ("septic", "Sewer / septic capacity is uncertain.", ["Whole-house Airbnb", "Wedding/private event"], "Obtain design, inspection, pumping, and permitted-capacity records."), ("internet", "Internet service availability is unknown.", ["Personal second home", "Whole-house Airbnb"], "Request address-level provider availability and speed evidence.")]:
        if (facts.get(key) or {}).get("value") is None: flags.append(_flag("Medium" if key in {"zoning", "str_regulations", "event_restrictions", "septic"} else "Low", basis, uses, [key], action))
    return flags


def derive_opportunities(prop: Property, facts: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    def add(title: str, basis: str, uses: list[str], sources: list[str]) -> None: items.append({"title": title, "factual_basis": basis, "affected_use_cases": uses, "source_fields": sources})
    nyc = ((facts.get("nyc_drive_time") or {}).get("value") or {}).get("drive_time_minutes")
    if isinstance(nyc, (int, float)) and nyc <= 150: add("Strong NYC access", f"Stored route duration is {nyc} minutes.", ["Personal second home", "Whole-house Airbnb"], ["nyc_drive_time"])
    train = (facts.get("nearest_amtrak") or {}).get("value") or {}
    if train.get("name"): add("Nearby train service", f"Provider returned {train['name']} as the nearest passenger station.", ["Personal second home", "Whole-house Airbnb", "Wedding/private event"], ["nearest_amtrak"])
    restaurant = (facts.get("restaurant_hub") or {}).get("value") or {}
    if restaurant.get("name"): add("Restaurant-town proximity", f"Provider returned {restaurant['name']} as a nearby restaurant candidate.", ["Personal second home", "Whole-house Airbnb"], ["restaurant_hub"])
    if prop.acreage is not None and prop.acreage >= 5: add("Land-based diligence potential", f"The stored property record reports {prop.acreage:g} acres.", ["Wedding/private event"], ["confirmed_acreage"])
    str_value = (facts.get("str_regulations") or {}).get("value")
    if isinstance(str_value, dict) and str_value.get("status") in {"allowed", "permitted"}: add("Favorable STR status", f"Stored STR status is {str_value['status']}.", ["Whole-house Airbnb"], ["str_regulations"])
    return items
