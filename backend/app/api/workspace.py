from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.acquisition import PropertyDocument, PropertyNote, PropertyTask
from app.models.property import Property
from app.schemas.acquisition import (
    NoteCreate,
    NoteRead,
    PropertyDocumentRead,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)

router = APIRouter(prefix="/properties/{property_id}", tags=["workspace"])
DOCUMENT_TYPES = {"inspection", "survey", "permit", "photo", "floor_plan"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("/documents", response_model=PropertyDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    property_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> PropertyDocument:
    _get_property(property_id, db)
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"document_type must be one of {sorted(DOCUMENT_TYPES)}")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 25 MB limit")
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "document").suffix.lower()
    stored_filename = f"{property_id}-{uuid4().hex}{suffix}"
    (upload_dir / stored_filename).write_bytes(content)
    record = PropertyDocument(
        property_id=property_id,
        filename=Path(file.filename or "document").name,
        stored_filename=stored_filename,
        document_type=document_type,
        content_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/documents", response_model=list[PropertyDocumentRead])
def list_documents(property_id: int, db: Session = Depends(get_db)) -> list[PropertyDocument]:
    _get_property(property_id, db)
    return list(db.scalars(select(PropertyDocument).where(PropertyDocument.property_id == property_id)))


@router.get("/documents/{document_id}/download")
def download_document(property_id: int, document_id: int, db: Session = Depends(get_db)) -> FileResponse:
    record = _get_child(PropertyDocument, document_id, property_id, db)
    path = Path(get_settings().upload_dir) / record.stored_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document file is missing")
    return FileResponse(path, media_type=record.content_type, filename=record.filename)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(property_id: int, document_id: int, db: Session = Depends(get_db)) -> None:
    record = _get_child(PropertyDocument, document_id, property_id, db)
    path = Path(get_settings().upload_dir) / record.stored_filename
    path.unlink(missing_ok=True)
    db.delete(record)
    db.commit()


@router.post("/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(property_id: int, payload: NoteCreate, db: Session = Depends(get_db)) -> PropertyNote:
    _get_property(property_id, db)
    note = PropertyNote(property_id=property_id, **payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("/notes", response_model=list[NoteRead])
def list_notes(property_id: int, db: Session = Depends(get_db)) -> list[PropertyNote]:
    _get_property(property_id, db)
    query = select(PropertyNote).where(PropertyNote.property_id == property_id).order_by(PropertyNote.created_at.desc())
    return list(db.scalars(query))


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(property_id: int, note_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get_child(PropertyNote, note_id, property_id, db))
    db.commit()


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(property_id: int, payload: TaskCreate, db: Session = Depends(get_db)) -> PropertyTask:
    _get_property(property_id, db)
    task = PropertyTask(property_id=property_id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(property_id: int, db: Session = Depends(get_db)) -> list[PropertyTask]:
    _get_property(property_id, db)
    query = select(PropertyTask).where(PropertyTask.property_id == property_id).order_by(PropertyTask.created_at.desc())
    return list(db.scalars(query))


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(property_id: int, task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)) -> PropertyTask:
    task = _get_child(PropertyTask, task_id, property_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(property_id: int, task_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get_child(PropertyTask, task_id, property_id, db))
    db.commit()


def _get_property(property_id: int, db: Session) -> Property:
    prop = db.get(Property, property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


def _get_child(model: type, item_id: int, property_id: int, db: Session):
    record = db.get(model, item_id)
    if record is None or record.property_id != property_id:
        raise HTTPException(status_code=404, detail="Resource not found")
    return record
