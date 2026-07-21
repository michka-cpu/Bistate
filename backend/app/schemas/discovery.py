from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ListingSearch(BaseModel):
    county: str | None = Field(default=None, max_length=150)
    town: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    min_acreage: float | None = Field(default=None, ge=0)
    bedrooms: float | None = Field(default=None, ge=0)
    property_type: str | None = Field(default=None, max_length=100)


class DiscoveredListingRead(BaseModel):
    id: int; listing_source: str; listing_url: str | None; address: str; city: str; state: str
    postal_code: str | None; county: str | None; asking_price: float | None; acreage: float | None
    bedrooms: float | None; bathrooms: float | None; property_type: str | None; photo_url: str | None
    listing_date: datetime | None; is_watchlisted: bool
    model_config = ConfigDict(from_attributes=True)


class WatchlistUpdate(BaseModel):
    is_watchlisted: bool
