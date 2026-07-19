from typing import Any

from app.models.property import Property
from app.schemas.underwriting import UnderwritingInputs
from app.services.underwriting import calculate


def underwrite_property(prop: Property) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if prop.asking_price is not None:
        payload["purchase_price"] = float(prop.asking_price)
    if prop.annual_taxes is not None:
        payload["property_tax"] = float(prop.annual_taxes)
    result = calculate(UnderwritingInputs(**payload)).model_dump(mode="json")
    dashboard = result["dashboard"]
    dscr = dashboard["dscr"]
    coc = dashboard["cash_on_cash_return"]
    buy_score = _bounded(50 + coc * 180 + (dscr - 1) * 25)
    airbnb_score = _enrichment_score(prop, "airbnb_suitability", 50)
    wedding_score = _enrichment_score(prop, "wedding_suitability", 50)
    personal_use_score = _bounded(55 + (10 if prop.bedrooms and prop.bedrooms >= 3 else 0))
    confidence = _confidence(prop)
    scores = {
        "buy_score": buy_score,
        "airbnb_score": airbnb_score,
        "wedding_score": wedding_score,
        "personal_use_score": personal_use_score,
        "overall_score": round((buy_score * 0.4 + airbnb_score * 0.25 + wedding_score * 0.25 + personal_use_score * 0.1), 1),
        "confidence_score": confidence,
    }
    return {"output": result, "assumptions": result["assumptions"], "scores": scores}


def build_investment_memo(prop: Property) -> dict[str, Any]:
    output = prop.underwriting_output or {}
    dashboard = output.get("dashboard", {})
    enrichment = prop.enrichment_data or {}
    missing = [key for key, item in enrichment.items() if item.get("value") is None]
    for key in ("asking_price", "annual_taxes", "latitude", "longitude", "acreage", "bedrooms", "bathrooms", "square_feet"):
        if getattr(prop, key) is None:
            missing.append(key)
    strengths = []
    weaknesses = []
    if (prop.overall_score or 0) >= 70:
        strengths.append("Overall acquisition score is above the approval benchmark.")
    if dashboard.get("dscr", 0) >= 1.25:
        strengths.append("Debt service coverage is at or above 1.25x.")
    else:
        weaknesses.append("Debt service coverage is below the 1.25x target.")
    if dashboard.get("cash_on_cash_return", 0) > 0:
        strengths.append("Base-case workbook cash-on-cash return is positive.")
    else:
        weaknesses.append("Base-case workbook cash-on-cash return is negative.")
    return {
        "property_id": prop.id,
        "executive_summary": f"{prop.name} has an overall Bistate score of {prop.overall_score or 0:.1f}/100. Financial figures are persisted from the workbook underwriting engine.",
        "strengths": strengths,
        "weaknesses": weaknesses,
        "risks": ["Provider-backed facts require verification before acquisition."] + (["Material information is missing."] if missing else []),
        "renovation_summary": output.get("renovation", {}),
        "financial_summary": dashboard,
        "cash_required": dashboard.get("total_cash_required", 0),
        "projected_returns": output.get("projection", {}),
        "sensitivity_summary": output.get("sensitivity", {}),
        "underwriting_explanation": output.get("traceability", {}),
        "assumptions_used": prop.underwriting_assumptions or {},
        "comparable_properties": [
            {"address": item.address, "sale_price": float(item.sale_price) if item.sale_price else None, "square_feet": item.square_feet}
            for item in prop.comparable_properties
        ],
        "missing_information": sorted(set(missing)),
        "confidence_score": prop.confidence_score or 0,
    }


def _bounded(value: float) -> float:
    return round(max(0, min(100, value)), 1)


def _enrichment_score(prop: Property, key: str, fallback: float) -> float:
    value = (prop.enrichment_data or {}).get(key, {}).get("value")
    return _bounded(float(value)) if value is not None else fallback


def _confidence(prop: Property) -> float:
    enrichments = list((prop.enrichment_data or {}).values())
    enrichment_confidence = sum(item.get("confidence", 0) for item in enrichments) / max(1, len(enrichments))
    core = [prop.asking_price, prop.annual_taxes, prop.acreage, prop.bedrooms, prop.bathrooms, prop.square_feet]
    completeness = sum(value is not None for value in core) / len(core)
    return round((enrichment_confidence * 0.6 + completeness * 0.4) * 100, 1)
