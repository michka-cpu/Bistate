"""Comparable scoring and valuation over approved, persisted sale records.

Collection remains provider-gated: no records are synthesized when a licensed/public
county adapter is unavailable. Valuation uses only persisted comparable records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from statistics import median
from typing import Any

from app.models.comparable_property import ComparableProperty
from app.models.property import Property


def collect_comparables(prop: Property) -> list[ComparableProperty]:
    """Hook for approved county/licensed adapters; intentionally never fabricates sales."""
    return []


def similarity_score(subject: Property, comparable: ComparableProperty) -> float:
    """Weighted distance and physical-attribute similarity, bounded 0–100."""
    factors: list[tuple[float, float]] = []
    if comparable.distance_miles is not None: factors.append((0.30, max(0, 1 - comparable.distance_miles / 25)))
    for weight, subject_value, comp_value, scale in (
        (0.22, subject.square_feet, comparable.square_feet, max(subject.square_feet or 1, 1)),
        (0.14, subject.acreage, comparable.acreage, max(subject.acreage or 1, 1)),
        (0.12, subject.bedrooms, comparable.bedrooms, 5),
        (0.10, subject.bathrooms, comparable.bathrooms, 4),
        (0.12, subject.year_built, comparable.year_built, 50),
    ):
        if subject_value is not None and comp_value is not None:
            factors.append((weight, max(0, 1 - abs(float(subject_value) - float(comp_value)) / scale)))
    if not factors: return 0.0
    total_weight = sum(weight for weight, _ in factors)
    return round(sum(weight * score for weight, score in factors) / total_weight * 100, 1)


def valuation(subject: Property, comparables: list[ComparableProperty]) -> dict[str, Any]:
    verified = [c for c in comparables if c.verification_status == "verified" and c.sale_price]
    if not verified:
        return {"estimated_market_value": None, "estimated_value_range": None, "price_per_square_foot": None, "price_per_acre": None, "confidence": 0, "methodology": "No verified comparable sales are available from an approved provider.", "missing_reason": "Verified comparable sales are unavailable"}
    weighted_values: list[tuple[float, float]] = []
    for comp in verified:
        score = similarity_score(subject, comp)
        comp.similarity_score = score
        if subject.square_feet and comp.price_per_square_foot:
            value = float(comp.price_per_square_foot) * subject.square_feet
        elif subject.acreage and comp.price_per_acre:
            value = float(comp.price_per_acre) * subject.acreage
        else: value = float(comp.sale_price)
        weighted_values.append((value, max(score, 1)))
    estimate = sum(value * weight for value, weight in weighted_values) / sum(weight for _, weight in weighted_values)
    values = [value for value, _ in weighted_values]
    confidence = round(min(100, sum(similarity_score(subject, c) for c in verified) / len(verified)) * min(1, len(verified) / 3), 1)
    return {"estimated_market_value": round(estimate, 2), "estimated_value_range": {"low": round(min(values), 2), "high": round(max(values), 2)}, "price_per_square_foot": round(estimate / subject.square_feet, 2) if subject.square_feet else None, "price_per_acre": round(estimate / subject.acreage, 2) if subject.acreage else None, "confidence": confidence, "methodology": "Similarity-weighted estimate from verified persisted comparable sales using distance, size, acreage, beds, baths, and year built.", "missing_reason": None}


def comparable_payload(subject: Property) -> dict[str, Any]:
    records = list(subject.comparable_properties)
    items = []
    for record in records:
        record.similarity_score = similarity_score(subject, record)
        items.append({"address": record.address, "sale_price": float(record.sale_price) if record.sale_price else None, "sale_date": record.sale_date, "distance": record.distance_miles, "square_feet": record.square_feet, "acreage": record.acreage, "bedrooms": record.bedrooms, "bathrooms": record.bathrooms, "year_built": record.year_built, "latitude": record.latitude, "longitude": record.longitude, "similarity_score": record.similarity_score, "source": record.source, "verification_status": record.verification_status, "last_updated": record.last_updated})
    return {"comparables": items, "valuation": valuation(subject, records), "confidence": valuation(subject, records)["confidence"], "methodology": "Only verified sales from approved providers contribute to valuation."}
