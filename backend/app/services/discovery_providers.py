"""Provider adapters for discovery. Replace each adapter's fetch method with licensed API calls."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.schemas.discovery import ListingSearch


@dataclass(frozen=True)
class ProviderListing:
    external_id: str; source: str; url: str; address: str; city: str; state: str; postal_code: str
    county: str; asking_price: float; acreage: float; bedrooms: float; bathrooms: float; property_type: str
    photo_url: str; listing_date: datetime


class DiscoveryProvider:
    source = ""
    def search(self, filters: ListingSearch) -> list[ProviderListing]: return []


class SampleDiscoveryProvider(DiscoveryProvider):
    def __init__(self, source: str, offset: int): self.source, self.offset = source, offset
    def search(self, filters: ListingSearch) -> list[ProviderListing]:
        # Adapter-shaped sample data makes search usable without scraping or unlicensed feeds.
        listing = ProviderListing(
            external_id=f"{self.source.lower()}-hudson-{self.offset}", source=self.source,
            url=f"https://www.{self.source.lower()}.com/listing/hudson-{self.offset}",
            address=f"{18 + self.offset} River Road", city="Hudson", state="NY", postal_code="12534",
            county="Columbia", asking_price=475000 + self.offset * 25000, acreage=4.2 + self.offset,
            bedrooms=3, bathrooms=2.5, property_type="Single Family",
            photo_url=f"https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
            listing_date=datetime.now(timezone.utc) - timedelta(days=self.offset + 1),
        )
        return [listing] if listing_matches_filters(listing, filters) else []


def listing_matches_filters(item: Any, f: ListingSearch) -> bool:
    """Return True when a listing satisfies every submitted filter.

    Works for both provider sample listings and persisted ``DiscoveredListing`` rows,
    which share these attribute names. Fields absent on the listing (None) never match a
    filter that constrains them, so stale rows are excluded rather than leaking through.
    """
    def text_contains(needle: str | None, haystack: str | None) -> bool:
        if not needle: return True
        return haystack is not None and needle.lower() in haystack.lower()

    def at_least(minimum: float | None, value: float | None) -> bool:
        if minimum is None: return True
        return value is not None and value >= minimum

    def at_most(maximum: float | None, value: float | None) -> bool:
        if maximum is None: return True
        return value is not None and value <= maximum

    return (
        text_contains(f.county, item.county)
        and text_contains(f.town, item.city)
        and (not f.postal_code or f.postal_code == item.postal_code)
        and at_least(f.min_price, item.asking_price)
        and at_most(f.max_price, item.asking_price)
        and at_least(f.min_acreage, item.acreage)
        and at_least(f.bedrooms, item.bedrooms)
        and (not f.property_type or (item.property_type is not None and f.property_type.lower() == item.property_type.lower()))
    )


PROVIDERS = [SampleDiscoveryProvider(source, index) for index, source in enumerate(("Zillow", "Realtor", "Redfin", "LandWatch"))]
