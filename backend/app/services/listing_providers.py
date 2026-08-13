"""Normalize acquisition imports (address, listing URL, or MLS number).

The goal is an honest identity: when a URL only carries an opaque provider id we do
*not* fabricate a street address. Instead the listing is returned with
``needs_resolution=True`` and the raw ``provider_reference`` so the UI can show an
explicit "Listing information incomplete" state and offer a resolve/retry action.
"""
from dataclasses import dataclass
import re
from urllib.parse import unquote, urlparse

from app.schemas.acquisition import PropertyImport

# Sentinels used when a locality cannot be resolved. They exist only to satisfy the
# non-null model columns; the API exposes ``listing_incomplete`` so the UI never
# presents these as real values.
UNKNOWN_CITY = "Unknown"
UNKNOWN_STATE = "NA"

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

# Segments that are provider routing noise rather than address content.
_PATH_NOISE = {
    "homedetails", "homes", "home", "realestateandhomes-detail", "property",
    "listing", "listings", "for_sale", "for-sale", "detail", "details", "b", "rooms",
}


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
    needs_resolution: bool = False
    provider_reference: str | None = None


class ListingProvider:
    source = "manual"

    def supports(self, host: str) -> bool:
        return False

    def extract_reference(self, segments: list[str]) -> str | None:
        """Return the provider id embedded in the URL path, if recognizable."""
        for segment in reversed(segments):
            if _looks_like_provider_id(segment):
                return _clean_reference(segment)
        return None

    def address_slug(self, segments: list[str]) -> str | None:
        """Return the URL path segment most likely to hold the street address."""
        candidates = [
            segment for segment in segments
            if segment.lower() not in _PATH_NOISE and not _looks_like_provider_id(segment)
        ]
        for segment in candidates:
            if _slug_has_street_number(segment):
                return segment
        return None

    def normalize(self, payload: PropertyImport) -> NormalizedListing:
        # A typed address is authoritative user intent; trust it.
        if payload.raw_address:
            street, city, state, postal_code = _parse_address(payload.raw_address)
            incomplete = not _has_street_number(street)
            return NormalizedListing(
                name=street or payload.raw_address.strip(),
                address=street or payload.raw_address.strip(),
                city=city, state=state, postal_code=postal_code,
                listing_source=self.source,
                listing_url=str(payload.listing_url) if payload.listing_url else None,
                mls_number=payload.mls_number,
                needs_resolution=incomplete,
            )

        if payload.listing_url:
            return self._normalize_url(payload)

        # MLS-only import: we have an identifier but no address to resolve yet.
        reference = (payload.mls_number or "").strip()
        return NormalizedListing(
            name=f"MLS {reference}" if reference else "Imported property",
            address=UNKNOWN_CITY, city=UNKNOWN_CITY, state=UNKNOWN_STATE,
            postal_code=None, listing_source=self.source, listing_url=None,
            mls_number=payload.mls_number or None,
            needs_resolution=True, provider_reference=reference or None,
        )

    def _normalize_url(self, payload: PropertyImport) -> NormalizedListing:
        segments = _path_segments(str(payload.listing_url))
        slug = self.address_slug(segments)
        if slug:
            street, city, state, postal_code = _address_from_slug(slug)
            if _has_street_number(street):
                # Some providers (e.g. Redfin: /NY/Hudson/<addr>/home/<id>) keep the
                # locality in earlier path segments; recover it when the slug lacked one.
                if state == UNKNOWN_STATE or city == UNKNOWN_CITY:
                    recovered_city, recovered_state = _locality_from_segments(segments, slug)
                    city = recovered_city if city == UNKNOWN_CITY else city
                    state = recovered_state if state == UNKNOWN_STATE else state
                return NormalizedListing(
                    name=street, address=street, city=city, state=state,
                    postal_code=postal_code, listing_source=self.source,
                    listing_url=str(payload.listing_url), mls_number=payload.mls_number,
                    needs_resolution=False,
                )
        # No street address could be recovered from the URL — do not invent one.
        reference = self.extract_reference(segments) or (segments[-1] if segments else None)
        label = f"{self.source} listing {reference}" if reference else f"{self.source} listing"
        return NormalizedListing(
            name=label, address=UNKNOWN_CITY, city=UNKNOWN_CITY, state=UNKNOWN_STATE,
            postal_code=None, listing_source=self.source,
            listing_url=str(payload.listing_url), mls_number=payload.mls_number,
            needs_resolution=True, provider_reference=reference,
        )


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
    DomainListingProvider("LandWatch", ("landwatch.com",)),
    DomainListingProvider("Airbnb", ("airbnb.com",)),
    DomainListingProvider("LoopNet", ("loopnet.com",)),
]

SUPPORTED_HOSTS = tuple(domain for provider in PROVIDERS for domain in provider.domains)


def normalize_listing(payload: PropertyImport) -> NormalizedListing:
    host = urlparse(str(payload.listing_url)).hostname or "" if payload.listing_url else ""
    provider = next((item for item in PROVIDERS if item.supports(host.lower())), ListingProvider())
    return provider.normalize(payload)


def _path_segments(url: str) -> list[str]:
    return [segment for segment in unquote(urlparse(url).path).strip("/").split("/") if segment]


def _clean_reference(segment: str) -> str:
    return re.sub(r"_zpid$", "", segment, flags=re.IGNORECASE)


def _looks_like_provider_id(segment: str) -> bool:
    lowered = segment.lower()
    return bool(
        re.fullmatch(r"\d+", segment)                 # 215394889
        or re.search(r"_zpid$", lowered)              # 215394889_zpid
        or re.fullmatch(r"m?\d{5,}-?\d*", lowered)    # M1234-56789 (realtor)
        or re.fullmatch(r"[0-9a-f]{16,}", lowered)    # long opaque hash
    )


def _slug_has_street_number(segment: str) -> bool:
    return _has_street_number(segment.replace("-", " ").replace("_", " "))


def _has_street_number(value: str) -> bool:
    """A resolvable street address begins with a house number."""
    return bool(re.match(r"^\s*\d+\s+\S", value or ""))


def _locality_from_segments(segments: list[str], address_slug: str) -> tuple[str, str]:
    """Recover (city, state) from path segments, e.g. Redfin's ``/NY/Hudson/<addr>/…``."""
    city, state = UNKNOWN_CITY, UNKNOWN_STATE
    for index, segment in enumerate(segments):
        if segment == address_slug:
            continue
        if segment.upper() in _US_STATES:
            state = segment.upper()
            following = segments[index + 1] if index + 1 < len(segments) else ""
            if following and following != address_slug and following.lower() not in _PATH_NOISE and not _looks_like_provider_id(following):
                city = following.replace("-", " ").replace("_", " ").title()
            break
    return city, state


def _address_from_slug(slug: str) -> tuple[str, str, str, str | None]:
    """Turn ``123-Main-St-Hudson-NY-12534`` (or ``_`` separated) into address parts."""
    # Drop a trailing Realtor-style listing id (``_M12345-67890``) before tokenizing.
    slug = re.sub(r"_m\d+(?:-\d+)?$", "", slug, flags=re.IGNORECASE)
    tokens = [token for token in re.split(r"[-_]", slug) if token]
    postal_code = None
    if tokens and re.fullmatch(r"\d{5}(?:-\d{4})?", tokens[-1]):
        postal_code = tokens.pop()
    state = UNKNOWN_STATE
    city = UNKNOWN_CITY
    if tokens and tokens[-1].upper() in _US_STATES:
        state = tokens.pop().upper()
        # Heuristic: the token before the state is the city.
        if tokens and not tokens[-1].isdigit():
            city = tokens.pop().replace("+", " ").title()
    street = " ".join(tokens).title()
    return street, city, state, postal_code


def _parse_address(raw: str) -> tuple[str, str, str, str | None]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    street = parts[0] if parts else raw.strip()
    city = parts[1] if len(parts) > 1 else UNKNOWN_CITY
    state_zip = parts[2].split() if len(parts) > 2 else []
    state = state_zip[0].upper()[:2] if state_zip else UNKNOWN_STATE
    postal_code = state_zip[1] if len(state_zip) > 1 else None
    return street, city, state, postal_code
