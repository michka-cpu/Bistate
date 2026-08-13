from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.property import Property
from app.models.acquisition import PropertyActivityEvent
from app.schemas.acquisition import InvestmentMemo, PropertyImport
from app.schemas.property import PropertyRead
from app.schemas.underwriting import UnderwritingResult
from app.services.acquisition import build_investment_memo, underwrite_property
from app.services.enrichment import enrich_property, provider_health
from app.services.property_intelligence import build_property_intelligence
from app.services.listing_providers import NormalizedListing, normalize_listing
from app.services.comparables import collect_comparables
from app.services.valuation import value_property

router = APIRouter(prefix="/properties", tags=["acquisition"])


class ResolveRequest(BaseModel):
    """Optionally supply the missing street address for an incomplete listing.

    With no address we re-parse the stored listing URL (a "retry"); with an address
    the user completes the record directly. We never invent an address."""

    raw_address: str | None = Field(default=None, max_length=500)


@router.post("/import", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
def import_property(payload: PropertyImport, db: Session = Depends(get_db)) -> Property:
    listing = normalize_listing(payload)
    duplicate = _find_duplicate(listing, db)
    if duplicate is not None:
        raise HTTPException(status_code=409, detail=f"Property already exists (id={duplicate.id})")
    prop = Property(
        name=listing.name,
        address=listing.address,
        city=listing.city,
        state=listing.state,
        postal_code=listing.postal_code,
        listing_source=listing.listing_source,
        listing_url=listing.listing_url,
        mls_number=listing.mls_number,
        status="Underwriting",
    )
    db.add(prop)
    db.flush()
    _run_pipeline(prop)
    message = "Property imported (listing information incomplete)" if listing.needs_resolution else "Property imported"
    db.add(PropertyActivityEvent(property_id=prop.id, event_type="imported", message=message))
    # An unresolved listing needs an address before diligence can be trusted.
    prop.status = "Needs Info" if listing.needs_resolution else "Reviewing"
    db.commit()
    db.refresh(prop)
    return prop


@router.post("/{property_id}/resolve", response_model=PropertyRead)
def resolve_listing(property_id: int, payload: ResolveRequest, db: Session = Depends(get_db)) -> Property:
    """Resolve an incomplete listing: apply a supplied address, otherwise re-parse the
    stored listing URL, then re-run analysis. Returns the (possibly still incomplete) record."""
    prop = _get_property(property_id, db)
    listing: NormalizedListing | None = None
    if payload.raw_address and payload.raw_address.strip():
        listing = normalize_listing(PropertyImport(raw_address=payload.raw_address.strip()))
    elif prop.listing_url:
        listing = normalize_listing(PropertyImport(listing_url=prop.listing_url))
    if listing is not None and not listing.needs_resolution:
        prop.name, prop.address = listing.name, listing.address
        prop.city, prop.state = listing.city, listing.state
        prop.postal_code = listing.postal_code or prop.postal_code
        _run_pipeline(prop, refresh=True)
        prop.status = "Reviewing"
        db.add(PropertyActivityEvent(property_id=prop.id, event_type="resolved", message=f"Listing resolved to {prop.address}"))
    else:
        db.add(PropertyActivityEvent(property_id=prop.id, event_type="resolve_failed", message="Listing could not be resolved automatically; a full address is required"))
    db.commit()
    db.refresh(prop)
    return prop


@router.post("/{property_id}/enrich", response_model=PropertyRead)
def refresh_enrichment(property_id: int, db: Session = Depends(get_db)) -> Property:
    prop = _get_property(property_id, db)
    data, errors = enrich_property(prop, refresh=True)
    prop.enrichment_data = data
    prop.provider_errors = {**(prop.provider_errors or {}), **errors}
    prop.pipeline_state = {**(prop.pipeline_state or {}), "enrich": "completed"}
    db.commit()
    db.refresh(prop)
    return prop


@router.post("/{property_id}/underwrite", response_model=UnderwritingResult)
def refresh_underwriting(property_id: int, db: Session = Depends(get_db)) -> dict:
    prop = _get_property(property_id, db)
    package = underwrite_property(prop)
    prop.underwriting_output = package["output"]
    prop.underwriting_assumptions = package["assumptions"]
    for field, value in package["scores"].items():
        setattr(prop, field, value)
    db.commit()
    return package["output"]


@router.get("/{property_id}/report", response_model=InvestmentMemo)
def get_investment_memo(property_id: int, db: Session = Depends(get_db)) -> dict:
    prop = _get_property(property_id, db)
    if not prop.underwriting_output:
        raise HTTPException(status_code=409, detail="Property has not been underwritten")
    return build_investment_memo(prop)


@router.post("/{property_id}/refresh", response_model=PropertyRead)
def refresh_analysis(property_id: int, db: Session = Depends(get_db)) -> Property:
    prop = _get_property(property_id, db)
    _run_pipeline(prop, refresh=True)
    db.commit(); db.refresh(prop)
    return prop


@router.get("/providers/health")
def get_provider_health() -> list[dict]:
    return provider_health()


@router.get("/{property_id}/intelligence")
def get_property_intelligence(property_id: int, db: Session = Depends(get_db)) -> dict:
    """Return coverage and explainability without changing underwriting output."""
    return build_property_intelligence(_get_property(property_id, db))


def _run_pipeline(prop: Property, refresh: bool = False) -> None:
    prop.pipeline_state = {"normalize": "completed", "import": "completed", "enrich": "running", "comparables": "pending", "underwrite": "pending", "memo": "pending"}
    data, errors = enrich_property(prop, refresh=refresh)
    prop.enrichment_data = data
    prop.provider_errors = {**(prop.provider_errors or {}), **errors}
    prop.pipeline_state["enrich"] = "completed"
    # This only persists records returned by an approved live/licensed adapter.
    if refresh:
        for comparable in list(prop.comparable_properties):
            prop.comparable_properties.remove(comparable)
    for comparable in collect_comparables(prop):
        prop.comparable_properties.append(comparable)
    prop.pipeline_state["comparables"] = "completed"
    # Valuation is retained as explainability; calibrated underwriting scores are unchanged.
    prop.valuation_data = value_property(prop)
    prop.pipeline_state["underwrite"] = "running"
    package = underwrite_property(prop)
    prop.underwriting_output = package["output"]
    prop.underwriting_assumptions = package["assumptions"]
    for field, value in package["scores"].items():
        setattr(prop, field, value)
    prop.pipeline_state["underwrite"] = "completed"
    prop.pipeline_state["memo"] = "completed"
    prop.activity_events.append(PropertyActivityEvent(event_type="refreshed" if refresh else "analyzed", message="Analysis completed"))


def _normalize_address(value: str | None) -> str:
    """Casefold, strip punctuation, and collapse whitespace so that addresses differing
    only by capitalization, punctuation, or spacing compare equal for de-duplication."""
    if not value:
        return ""
    stripped = "".join(char if char.isalnum() or char.isspace() else " " for char in value)
    return " ".join(stripped.split()).casefold()


def _find_duplicate(listing, db: Session) -> Property | None:
    """Return an existing property that matches by listing URL or by normalized address."""
    if listing.listing_url:
        by_url = db.scalar(select(Property).where(Property.listing_url == listing.listing_url))
        if by_url is not None:
            return by_url
    # Unresolved listings share a placeholder address (Unknown/NA); matching on it would
    # wrongly collapse distinct incomplete listings together. De-duplicate them by URL only.
    if getattr(listing, "needs_resolution", False):
        return None
    target = _normalize_address(listing.address)
    if not target:
        return None
    state = (listing.state or "").casefold()
    city = _normalize_address(listing.city)
    for candidate in db.scalars(select(Property)):
        if (
            _normalize_address(candidate.address) == target
            and _normalize_address(candidate.city) == city
            and (candidate.state or "").casefold() == state
        ):
            return candidate
    return None


def _get_property(property_id: int, db: Session) -> Property:
    prop = db.get(Property, property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop
