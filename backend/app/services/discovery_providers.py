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


# Illustrative sample inventory spanning Bistate's target Catskills markets (Sullivan and
# Delaware counties, plus Ulster and Columbia). This is placeholder discovery data — no
# licensed MLS/portal feed is connected — shaped like a real provider response so the
# Discovery search is usable for these markets today. Swap SampleDiscoveryProvider.search
# for licensed API calls to surface live listings. Monticello (Sullivan) is included by
# requirement. (city, county, postal_code, base_price, acreage, bedrooms, property_type)
SAMPLE_MARKETS: list[tuple[str, str, str, float, float, float, str]] = [
    ("Monticello", "Sullivan", "12701", 349000, 0.5, 3, "Single Family"),
    ("Liberty", "Sullivan", "12754", 415000, 2.0, 3, "Single Family"),
    ("Livingston Manor", "Sullivan", "12758", 525000, 5.0, 3, "Single Family"),
    ("Callicoon", "Sullivan", "12723", 675000, 8.0, 4, "Single Family"),
    ("Narrowsburg", "Sullivan", "12764", 599000, 3.0, 3, "Single Family"),
    ("Bethel", "Sullivan", "12720", 289000, 6.0, 0, "Land"),
    ("Delhi", "Delaware", "13753", 375000, 4.0, 3, "Single Family"),
    ("Margaretville", "Delaware", "12455", 445000, 3.0, 3, "Single Family"),
    ("Roxbury", "Delaware", "12474", 560000, 7.0, 4, "Single Family"),
    ("Andes", "Delaware", "13731", 629000, 10.0, 4, "Single Family"),
    ("Bovina Center", "Delaware", "13740", 720000, 12.0, 0, "Land"),
    ("Stamford", "Delaware", "12167", 315000, 1.5, 3, "Single Family"),
    ("Kingston", "Ulster", "12401", 485000, 0.3, 3, "Single Family"),
    ("New Paltz", "Ulster", "12561", 615000, 1.2, 4, "Single Family"),
    ("Woodstock", "Ulster", "12498", 799000, 2.5, 4, "Single Family"),
    ("Hudson", "Columbia", "12534", 475000, 4.2, 3, "Single Family"),
]


class SampleDiscoveryProvider(DiscoveryProvider):
    def __init__(self, source: str, offset: int): self.source, self.offset = source, offset
    def search(self, filters: ListingSearch) -> list[ProviderListing]:
        # Adapter-shaped sample data makes search usable without scraping or unlicensed
        # feeds. Each source emits one listing per target market; prices/ages are staggered
        # per source so the four adapters return distinct, deduplicated candidates.
        results: list[ProviderListing] = []
        for index, (city, county, postal_code, price, acreage, bedrooms, property_type) in enumerate(SAMPLE_MARKETS):
            listing = ProviderListing(
                external_id=f"{self.source.lower()}-{postal_code}-{index}", source=self.source,
                url=f"https://www.{self.source.lower()}.com/listing/{postal_code}-{index}",
                address=f"{18 + self.offset + index} Sample Road", city=city, state="NY", postal_code=postal_code,
                county=county, asking_price=price + self.offset * 10000, acreage=acreage,
                bedrooms=bedrooms, bathrooms=(bedrooms - 0.5 if bedrooms else 0), property_type=property_type,
                photo_url="https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
                listing_date=datetime.now(timezone.utc) - timedelta(days=index + self.offset + 1),
            )
            if listing_matches_filters(listing, filters):
                results.append(listing)
        return results


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
