"""Comparable-sales valuation with explicit inputs, adjustments, provenance, and cache metadata."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from app.config import get_settings
from app.models.comparable_property import ComparableProperty
from app.models.property import Property


def value_property(prop: Property, radius_miles: float = 10, sold_within_days: int = 180) -> dict:
    cutoff = date.today() - timedelta(days=sold_within_days)
    candidates = [c for c in prop.comparable_properties if c.sale_price and c.verification_status == "verified" and (c.distance_miles is None or c.distance_miles <= radius_miles) and (c.sale_date is None or c.sale_date >= cutoff)]
    rows = []
    for comp in candidates:
        score, adjustments = similarity(prop, comp)
        comp.similarity_score = score
        comp.adjustments = adjustments
        adjusted_price = float(comp.sale_price) * (1 + sum(item["percent"] for item in adjustments))
        rows.append((comp, adjusted_price))
    if not rows:
        return {"estimated_value": None, "value_range": None, "confidence_score": 0, "pricing_signal": "Unavailable", "discount_premium": None, "percent_difference": None, "comparables": [], "explanation": "No verified comparable sales matched the configured search.", "provenance": {"method": "weighted similarity", "radius_miles": radius_miles, "sold_within_days": sold_within_days, "retrieved_at": datetime.now(timezone.utc).isoformat(), "cache_ttl_seconds": get_settings().provider_cache_seconds}}
    weights = [max(comp.similarity_score or 0, 1) for comp, _ in rows]
    estimated = sum(price * weight for (_, price), weight in zip(rows, weights)) / sum(weights)
    prices = [price for _, price in rows]
    confidence = round(min(100, mean(weights) * min(1, len(rows) / 5)), 1)
    asking = float(prop.asking_price) if prop.asking_price else None
    difference = None if asking is None else estimated - asking
    percent = None if asking in (None, 0) else difference / asking * 100
    signal = "Unavailable" if percent is None else "Undervalued" if percent >= 5 else "Overpriced" if percent <= -5 else "Fair Value"
    return {"estimated_value": round(estimated, 2), "value_range": {"low": round(min(prices), 2), "high": round(max(prices), 2)}, "confidence_score": confidence, "pricing_signal": signal, "discount_premium": None if difference is None else round(difference, 2), "percent_difference": None if percent is None else round(percent, 2), "comparables": [serialize(comp, price) for comp, price in rows], "explanation": "Estimated value is the similarity-weighted average of verified, nearby sales after transparent feature adjustments. It is explainability only and does not alter calibrated underwriting weights.", "provenance": {"method": "weighted similarity", "radius_miles": radius_miles, "sold_within_days": sold_within_days, "retrieved_at": datetime.now(timezone.utc).isoformat(), "cache_ttl_seconds": get_settings().provider_cache_seconds}}


def similarity(prop: Property, comp: ComparableProperty) -> tuple[float, list[dict]]:
    checks = [("Property type", prop.property_type, comp.property_type, 30), ("Bedrooms", prop.bedrooms, comp.bedrooms, 15), ("Bathrooms", prop.bathrooms, comp.bathrooms, 15), ("Acreage", prop.acreage, comp.acreage, 15), ("Square feet", prop.square_feet, comp.square_feet, 15), ("Distance", 0, comp.distance_miles, 10)]
    score = 0.0; adjustments = []
    for label, subject, observed, weight in checks:
        if observed is None or subject is None: continue
        if label == "Property type":
            match = str(subject).lower() == str(observed).lower(); score += weight if match else 0
            if not match: adjustments.append({"field": label, "percent": -0.05, "reason": f"Different property type ({observed})"})
        elif label == "Distance": score += max(0, weight * (1 - float(observed) / 10))
        else:
            delta = abs(float(subject) - float(observed)) / max(float(subject), 1)
            score += max(0, weight * (1 - delta))
            if delta > .05: adjustments.append({"field": label, "percent": round((float(subject) - float(observed)) / max(float(observed), 1) * .02, 4), "reason": f"Subject {label.lower()} differs from comparable"})
    return round(score, 1), adjustments


def serialize(comp: ComparableProperty, adjusted_price: float) -> dict:
    return {"id": comp.id, "address": comp.address, "sale_price": float(comp.sale_price), "adjusted_price": round(adjusted_price, 2), "similarity_score": comp.similarity_score, "distance_miles": comp.distance_miles, "sale_date": comp.sale_date.isoformat() if comp.sale_date else None, "adjustments": comp.adjustments or [], "source": comp.source, "provenance": comp.provenance or {}}
