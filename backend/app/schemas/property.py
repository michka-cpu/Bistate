from datetime import datetime

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.schemas.acquisition import PipelineStatus

# Core inputs the calibrated underwriting engine needs to produce non-placeholder
# figures. When they are missing the model falls back to workbook defaults, so the
# financial dashboard must be labeled as an estimate rather than presented as fact.
CORE_INPUTS = ("asking_price", "annual_taxes", "acreage", "bedrooms", "bathrooms", "square_feet")


class PropertyBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    status: PipelineStatus = "New"
    listing_source: str | None = None
    listing_url: str | None = None
    mls_number: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    county: str | None = None
    property_type: str | None = None
    acreage: float | None = Field(default=None, ge=0)
    bedrooms: float | None = Field(default=None, ge=0)
    bathrooms: float | None = Field(default=None, ge=0)
    square_feet: int | None = Field(default=None, ge=0)
    asking_price: float | None = Field(default=None, ge=0)
    annual_taxes: float | None = Field(default=None, ge=0)
    hoa: float | None = Field(default=None, ge=0)
    year_built: int | None = Field(default=None, ge=0)
    parcel_id: str | None = None
    listing_status: str | None = None
    images: list[str] = Field(default_factory=list)
    description: str | None = None
    agent: dict[str, Any] | None = None


class PropertyCreate(PropertyBase):
    pass


class PropertyUpdate(BaseModel):
    is_favorite: bool | None = None
    is_pinned: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    status: PipelineStatus | None = None
    listing_source: str | None = None
    listing_url: str | None = None
    mls_number: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    county: str | None = None
    property_type: str | None = None
    acreage: float | None = Field(default=None, ge=0)
    bedrooms: float | None = Field(default=None, ge=0)
    bathrooms: float | None = Field(default=None, ge=0)
    square_feet: int | None = Field(default=None, ge=0)
    asking_price: float | None = Field(default=None, ge=0)
    annual_taxes: float | None = Field(default=None, ge=0)
    hoa: float | None = Field(default=None, ge=0)
    year_built: int | None = Field(default=None, ge=0)
    parcel_id: str | None = None
    listing_status: str | None = None
    images: list[str] | None = None
    description: str | None = None
    agent: dict[str, Any] | None = None


class PropertyRead(PropertyBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False
    is_pinned: bool = False
    enrichment_data: dict[str, Any] = Field(default_factory=dict)
    underwriting_output: dict[str, Any] | None = None
    underwriting_assumptions: dict[str, Any] | None = None
    overall_score: float | None = None
    buy_score: float | None = None
    airbnb_score: float | None = None
    wedding_score: float | None = None
    personal_use_score: float | None = None
    confidence_score: float | None = None
    pipeline_state: dict[str, Any] = Field(default_factory=dict)
    provider_errors: dict[str, Any] = Field(default_factory=dict)
    valuation_data: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def missing_core_inputs(self) -> list[str]:
        """Core underwriting inputs that are absent for this property."""
        return [field for field in CORE_INPUTS if getattr(self, field, None) is None]

    @computed_field
    @property
    def financials_are_estimates(self) -> bool:
        """True when workbook output exists but the purchase price (and other core
        inputs) were not supplied, so the figures come from workbook defaults."""
        return bool(self.underwriting_output) and self.asking_price is None

    @computed_field
    @property
    def listing_incomplete(self) -> bool:
        """True when the record lacks a resolved street identity. Covers newly
        imported provider-id-only URLs and legacy ``Unknown, NA`` rows alike."""
        placeholder_city = self.city in {"", "Unknown"}
        placeholder_state = (self.state or "").upper() in {"", "NA"}
        looks_like_reference = bool(
            re.search(r"\d+\s*zpid", self.name, flags=re.IGNORECASE)
            or re.search(r"\blisting\s+\d", self.name, flags=re.IGNORECASE)
            or re.fullmatch(r"\d+\s*zpid", self.address or "", flags=re.IGNORECASE)
        )
        return placeholder_state or placeholder_city or looks_like_reference
