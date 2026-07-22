from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import get_settings
from app.api.acquisition import _get_property
from app.schemas.valuation import ValuationRead, ValuationSearch
from app.services.valuation import value_property

router = APIRouter(prefix="/properties", tags=["valuation"])

@router.post("/{property_id}/valuation/search", response_model=ValuationRead)
def search_valuation(property_id: int, settings: ValuationSearch, db: Session = Depends(get_db)) -> dict:
    prop = _get_property(property_id, db)
    result = value_property(prop, settings.radius_miles, settings.sold_within_days)
    prop.valuation_data = result
    db.commit()
    return result

@router.get("/{property_id}/valuation", response_model=ValuationRead)
def get_valuation(property_id: int, db: Session = Depends(get_db)) -> dict:
    prop = _get_property(property_id, db)
    cached = prop.valuation_data or {}
    retrieved_at = (cached.get("provenance") or {}).get("retrieved_at")
    if retrieved_at:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(retrieved_at)).total_seconds()
            if age < (cached.get("provenance") or {}).get("cache_ttl_seconds", get_settings().provider_cache_seconds): return cached
        except ValueError: pass
    result = value_property(prop)
    prop.valuation_data = result; db.commit()
    return result
