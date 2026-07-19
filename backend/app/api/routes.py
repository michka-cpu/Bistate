from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertyRead, PropertyUpdate
from app.schemas.underwriting import UnderwritingInputs, UnderwritingResult
from app.services.underwriting import calculate

router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return the service status for uptime checks and the web dashboard."""
    return {"status": "ok"}


@router.post("/underwriting/calculate", response_model=UnderwritingResult, tags=["underwriting"])
def calculate_underwriting(payload: UnderwritingInputs) -> UnderwritingResult:
    """Calculate the primary workbook’s Scenario A underwriting outputs."""
    return calculate(payload)


@router.post("/properties", response_model=PropertyRead, status_code=status.HTTP_201_CREATED, tags=["properties"])
def create_property(payload: PropertyCreate, db: Session = Depends(get_db)) -> Property:
    property_record = Property(**payload.model_dump())
    db.add(property_record)
    db.commit()
    db.refresh(property_record)
    return property_record


@router.get("/properties", response_model=list[PropertyRead], tags=["properties"])
def list_properties(db: Session = Depends(get_db)) -> list[Property]:
    return list(db.scalars(select(Property).order_by(Property.created_at.desc())))


@router.get("/properties/{property_id}", response_model=PropertyRead, tags=["properties"])
def get_property(property_id: int, db: Session = Depends(get_db)) -> Property:
    return _get_property_or_404(property_id, db)


@router.put("/properties/{property_id}", response_model=PropertyRead, tags=["properties"])
def update_property(property_id: int, payload: PropertyUpdate, db: Session = Depends(get_db)) -> Property:
    property_record = _get_property_or_404(property_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(property_record, field, value)
    db.commit()
    db.refresh(property_record)
    return property_record


@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["properties"])
def delete_property(property_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(_get_property_or_404(property_id, db))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _get_property_or_404(property_id: int, db: Session) -> Property:
    property_record = db.get(Property, property_id)
    if property_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return property_record
