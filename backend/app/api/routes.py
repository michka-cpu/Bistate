from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from io import BytesIO
import csv
from app.models.acquisition import PropertyActivityEvent
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertyRead, PropertyUpdate
from app.schemas.underwriting import UnderwritingInputs, UnderwritingResult
from app.services.underwriting import calculate
from app.api.acquisition import router as acquisition_router
from app.api.workspace import router as workspace_router
from app.api.discovery import router as discovery_router
from app.api.valuation import router as valuation_router

router = APIRouter()
router.include_router(acquisition_router)
router.include_router(workspace_router)
router.include_router(discovery_router)
router.include_router(valuation_router)


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return the service status for uptime checks and the web dashboard."""
    return {"status": "ok"}


@router.post("/underwriting/calculate", response_model=UnderwritingResult, tags=["underwriting"])
def calculate_underwriting(payload: UnderwritingInputs) -> UnderwritingResult:
    """Calculate traceable Scenario A or B outputs from the primary workbook."""
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
    if "status" in payload.model_dump(exclude_unset=True):
        db.add(PropertyActivityEvent(property_id=property_id, event_type="status_changed", message=f"Acquisition status changed to {property_record.status}"))
    db.commit()
    db.refresh(property_record)
    return property_record


@router.get("/properties/{property_id}/exports/csv", tags=["properties"])
def export_property_csv(property_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    prop = _get_property_or_404(property_id, db)
    output = BytesIO(); text = output.write
    # CSV is generated from persisted values only.
    rows = [["property_id", "name", "address", "status", "asking_price", "overall_score", "irr"], [prop.id, prop.name, prop.address, prop.status, prop.asking_price or "", prop.overall_score or "", (prop.underwriting_output or {}).get("projection", {}).get("levered_irr", "")]]
    content = "\n".join(",".join(str(value).replace(",", " ") for value in row) for row in rows).encode()
    return StreamingResponse(iter([content]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=property-{prop.id}-summary.csv"})


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

@router.get("/properties/{property_id}/exports/pdf", tags=["properties"])
def export_investment_memo_pdf(property_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    """Render the persisted memo and underwriting facts as a PDF; absent values remain absent."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen.canvas import Canvas
    from app.services.acquisition import build_investment_memo
    prop = _get_property_or_404(property_id, db)
    if not prop.underwriting_output:
        raise HTTPException(status_code=409, detail="Property has not been underwritten")
    memo = build_investment_memo(prop)
    output = BytesIO(); canvas = Canvas(output, pagesize=letter); y = 750
    for line in [prop.name, prop.address, "Investment memo", memo["executive_summary"], *memo["strengths"], *memo["risks"]]:
        for segment in str(line).splitlines() or [""]:
            canvas.drawString(48, y, segment[:110]); y -= 18
            if y < 48: canvas.showPage(); y = 750
    canvas.save(); output.seek(0)
    return StreamingResponse(output, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=property-{prop.id}-memo.pdf"})


@router.get("/properties/{property_id}/exports/xlsx", tags=["properties"])
def export_property_workbook_summary(property_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    """Export persisted listing and workbook output; no absent values are invented."""
    from openpyxl import Workbook
    prop = _get_property_or_404(property_id, db)
    workbook = Workbook(); sheet = workbook.active; sheet.title = "Property Summary"
    sheet.append(["Field", "Value"])
    for key, value in [("Property", prop.name), ("Address", prop.address), ("Status", prop.status), ("Asking price", prop.asking_price), ("Overall score", prop.overall_score)]: sheet.append([key, value])
    output_sheet = workbook.create_sheet("Workbook Output"); output_sheet.append(["Metric", "Value"])
    for key, value in (prop.underwriting_output or {}).get("dashboard", {}).items(): output_sheet.append([key, value])
    output = BytesIO(); workbook.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=property-{prop.id}-workbook-summary.xlsx"})
