"""Provider adapters for discovery. Replace each adapter's fetch method with licensed API calls."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
        return [listing] if _matches(listing, filters) else []


def _matches(item: ProviderListing, f: ListingSearch) -> bool:
    return (not f.county or f.county.lower() in item.county.lower()) and (not f.town or f.town.lower() in item.city.lower()) and (not f.postal_code or f.postal_code == item.postal_code) and (f.min_price is None or item.asking_price >= f.min_price) and (f.max_price is None or item.asking_price <= f.max_price) and (f.min_acreage is None or item.acreage >= f.min_acreage) and (f.bedrooms is None or item.bedrooms >= f.bedrooms) and (not f.property_type or f.property_type.lower() == item.property_type.lower())


PROVIDERS = [SampleDiscoveryProvider(source, index) for index, source in enumerate(("Zillow", "Realtor", "Redfin", "LandWatch"))]
