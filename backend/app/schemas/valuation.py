from typing import Any
from pydantic import BaseModel, Field

class ValuationSearch(BaseModel):
    radius_miles: float = Field(default=10, gt=0, le=100)
    sold_within_days: int = Field(default=180, ge=1, le=3650)

class ValuationRead(BaseModel):
    estimated_value: float | None
    value_range: dict[str, float] | None
    confidence_score: float
    pricing_signal: str
    discount_premium: float | None
    percent_difference: float | None
    comparables: list[dict[str, Any]]
    explanation: str
    provenance: dict[str, Any]
