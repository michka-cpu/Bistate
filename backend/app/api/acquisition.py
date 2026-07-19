from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.property import Property
from app.schemas.acquisition import InvestmentMemo, PropertyImport
from app.schemas.property import PropertyRead
from app.schemas.underwriting import UnderwritingResult
from app.services.acquisition import build_investment_memo, underwrite_property
from app.services.enrichment import enrich_property, provider_health
from app.services.listing_providers import normalize_listing
from app.services.comparables import collect_comparables

router = APIRouter(prefix="/properties", tags=["acquisition"])


@router.post("/import", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
def import_property(payload: PropertyImport, db: Session = Depends(get_db)) -> Property:
    listing = normalize_listing(payload)
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
    prop.status = "Reviewing"
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
    prop.pipeline_state["underwrite"] = "running"
    package = underwrite_property(prop)
    prop.underwriting_output = package["output"]
    prop.underwriting_assumptions = package["assumptions"]
    for field, value in package["scores"].items():
        setattr(prop, field, value)
    prop.pipeline_state["underwrite"] = "completed"
    prop.pipeline_state["memo"] = "completed"


def _get_property(property_id: int, db: Session) -> Property:
    prop = db.get(Property, property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop
