from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


PipelineStatus = Literal[
    "New", "Reviewing", "Underwriting", "Needs Info", "Approved", "Rejected", "Under Contract", "Closed"
]


class PropertyImport(BaseModel):
    listing_url: HttpUrl | None = None
    raw_address: str | None = Field(default=None, max_length=500)
    mls_number: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_identifier(self) -> "PropertyImport":
        if not any((self.listing_url, self.raw_address, self.mls_number)):
            raise ValueError("Provide a listing_url, raw_address, or mls_number")
        return self


class EnrichmentField(BaseModel):
    value: Any = None
    source: str
    last_updated: datetime
    confidence: float = Field(ge=0, le=1)
    missing_reason: str | None = None


class PropertyDocumentRead(BaseModel):
    id: int
    property_id: int
    filename: str
    document_type: str
    content_type: str | None
    size_bytes: int
    uploaded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NoteCreate(BaseModel):
    body: str = Field(min_length=1)
    author: str | None = Field(default=None, max_length=255)


class NoteRead(NoteCreate):
    id: int
    property_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    assignee: str | None = Field(default=None, max_length=255)
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    assignee: str | None = Field(default=None, max_length=255)
    due_date: date | None = None
    completed: bool | None = None


class TaskRead(TaskCreate):
    id: int
    property_id: int
    completed: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InvestmentMemo(BaseModel):
    property_id: int
    executive_summary: str
    strengths: list[str]
    weaknesses: list[str]
    risks: list[str]
    renovation_summary: dict[str, Any]
    financial_summary: dict[str, Any]
    cash_required: float
    projected_returns: dict[str, Any]
    sensitivity_summary: dict[str, Any]
    underwriting_explanation: dict[str, Any]
    assumptions_used: dict[str, Any]
    comparable_properties: list[dict[str, Any]]
    missing_information: list[str]
    confidence_score: float
