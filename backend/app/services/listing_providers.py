from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from app.schemas.acquisition import PropertyImport


@dataclass(frozen=True)
class NormalizedListing:
    name: str
    address: str
    city: str
    state: str
    postal_code: str | None
    listing_source: str
    listing_url: str | None
    mls_number: str | None


class ListingProvider:
    source = "manual"

    def supports(self, host: str) -> bool:
        return False

    def normalize(self, payload: PropertyImport) -> NormalizedListing:
        address = payload.raw_address or self._address_from_url(payload) or f"MLS {payload.mls_number}"
        street, city, state, postal_code = _parse_address(address)
        return NormalizedListing(
            name=street or "Imported property",
            address=street or address,
            city=city,
            state=state,
            postal_code=postal_code,
            listing_source=self.source,
            listing_url=str(payload.listing_url) if payload.listing_url else None,
            mls_number=payload.mls_number,
        )

    @staticmethod
    def _address_from_url(payload: PropertyImport) -> str | None:
        if not payload.listing_url:
            return None
        slug = unquote(urlparse(str(payload.listing_url)).path).strip("/").split("/")[-1]
        cleaned = slug.replace("_", " ").replace("-", " ").strip()
        return cleaned.title() if cleaned else None


class DomainListingProvider(ListingProvider):
    def __init__(self, source: str, domains: tuple[str, ...]):
        self.source = source
        self.domains = domains

    def supports(self, host: str) -> bool:
        return any(host == domain or host.endswith(f".{domain}") for domain in self.domains)


PROVIDERS = [
    DomainListingProvider("Zillow", ("zillow.com",)),
    DomainListingProvider("Realtor", ("realtor.com",)),
    DomainListingProvider("Redfin", ("redfin.com",)),
    DomainListingProvider("Airbnb", ("airbnb.com",)),
    DomainListingProvider("LoopNet", ("loopnet.com",)),
]


def normalize_listing(payload: PropertyImport) -> NormalizedListing:
    host = urlparse(str(payload.listing_url)).hostname or "" if payload.listing_url else ""
    provider = next((item for item in PROVIDERS if item.supports(host.lower())), ListingProvider())
    return provider.normalize(payload)


def _parse_address(raw: str) -> tuple[str, str, str, str | None]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    street = parts[0] if parts else raw.strip()
    city = parts[1] if len(parts) > 1 else "Unknown"
    state_zip = parts[2].split() if len(parts) > 2 else []
    state = state_zip[0].upper()[:2] if state_zip else "NA"
    postal_code = state_zip[1] if len(state_zip) > 1 else None
    return street, city, state, postal_code
