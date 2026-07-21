from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.acquisition import _run_pipeline
from app.database import get_db
from app.models.acquisition import PropertyActivityEvent
from app.models.discovered_listing import DiscoveredListing
from app.models.property import Property
from app.schemas.discovery import DiscoveredListingRead, ListingSearch, WatchlistUpdate
from app.schemas.property import PropertyRead
from app.services.discovery_providers import PROVIDERS

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/search", response_model=list[DiscoveredListingRead])
def search_listings(filters: ListingSearch, db: Session = Depends(get_db)) -> list[DiscoveredListing]:
    for adapter in PROVIDERS:
        for item in adapter.search(filters):
            record = db.scalar(select(DiscoveredListing).where(DiscoveredListing.listing_source == item.source, DiscoveredListing.provider_listing_id == item.external_id))
            if record is None:
                record = DiscoveredListing(provider_listing_id=item.external_id, listing_source=item.source, listing_url=item.url, address=item.address, city=item.city, state=item.state, postal_code=item.postal_code, county=item.county, asking_price=item.asking_price, acreage=item.acreage, bedrooms=item.bedrooms, bathrooms=item.bathrooms, property_type=item.property_type, photo_url=item.photo_url, listing_date=item.listing_date)
                db.add(record)
    db.commit()
    return list(db.scalars(select(DiscoveredListing).order_by(DiscoveredListing.listing_date.desc())))


@router.get("/listings", response_model=list[DiscoveredListingRead])
def list_discovered(db: Session = Depends(get_db)) -> list[DiscoveredListing]:
    return list(db.scalars(select(DiscoveredListing).order_by(DiscoveredListing.listing_date.desc())))


@router.put("/listings/{listing_id}/watchlist", response_model=DiscoveredListingRead)
def set_watchlist(listing_id: int, payload: WatchlistUpdate, db: Session = Depends(get_db)) -> DiscoveredListing:
    listing = _listing_or_404(listing_id, db); listing.is_watchlisted = payload.is_watchlisted; db.commit(); db.refresh(listing); return listing


@router.post("/listings/{listing_id}/analyze", response_model=PropertyRead, status_code=201)
def analyze_listing(listing_id: int, db: Session = Depends(get_db)) -> Property:
    listing = _listing_or_404(listing_id, db)
    duplicate = db.scalar(select(Property).where(Property.listing_url == listing.listing_url))
    if duplicate: raise HTTPException(status_code=409, detail=f"Property already exists (id={duplicate.id})")
    prop = Property(name=listing.address, address=listing.address, city=listing.city, state=listing.state, postal_code=listing.postal_code, county=listing.county, asking_price=listing.asking_price, acreage=listing.acreage, bedrooms=listing.bedrooms, bathrooms=listing.bathrooms, listing_source=listing.listing_source, listing_url=listing.listing_url, images=[listing.photo_url] if listing.photo_url else [], status="Underwriting")
    db.add(prop); db.flush(); _run_pipeline(prop); db.add(PropertyActivityEvent(property_id=prop.id, event_type="imported", message="Property imported from discovery")); prop.status = "Reviewing"; db.commit(); db.refresh(prop); return prop


def _listing_or_404(listing_id: int, db: Session) -> DiscoveredListing:
    listing = db.get(DiscoveredListing, listing_id)
    if not listing: raise HTTPException(status_code=404, detail="Discovered listing not found")
    return listing
