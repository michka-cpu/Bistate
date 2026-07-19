from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.acquisition import PipelineStatus


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
    acreage: float | None = Field(default=None, ge=0)
    bedrooms: float | None = Field(default=None, ge=0)
    bathrooms: float | None = Field(default=None, ge=0)
    square_feet: int | None = Field(default=None, ge=0)
    asking_price: float | None = Field(default=None, ge=0)
    annual_taxes: float | None = Field(default=None, ge=0)
    images: list[str] = Field(default_factory=list)
    description: str | None = None
    agent: dict[str, Any] | None = None


class PropertyCreate(PropertyBase):
    pass


class PropertyUpdate(BaseModel):
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
    acreage: float | None = Field(default=None, ge=0)
    bedrooms: float | None = Field(default=None, ge=0)
    bathrooms: float | None = Field(default=None, ge=0)
    square_feet: int | None = Field(default=None, ge=0)
    asking_price: float | None = Field(default=None, ge=0)
    annual_taxes: float | None = Field(default=None, ge=0)
    images: list[str] | None = None
    description: str | None = None
    agent: dict[str, Any] | None = None


class PropertyRead(PropertyBase):
    id: int
    created_at: datetime
    updated_at: datetime
    enrichment_data: dict[str, Any] = Field(default_factory=dict)
    underwriting_output: dict[str, Any] | None = None
    underwriting_assumptions: dict[str, Any] | None = None
    overall_score: float | None = None
    buy_score: float | None = None
    airbnb_score: float | None = None
    wedding_score: float | None = None
    personal_use_score: float | None = None
    confidence_score: float | None = None

    model_config = ConfigDict(from_attributes=True)
