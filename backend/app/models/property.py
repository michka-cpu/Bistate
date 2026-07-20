from __future__ import annotations
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Property(Base):
    """A real-estate property tracked by Bistate."""

    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text())
    is_favorite: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="New")
    listing_source: Mapped[str | None] = mapped_column(String(100))
    listing_url: Mapped[str | None] = mapped_column(String(2000))
    mls_number: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Float())
    longitude: Mapped[float | None] = mapped_column(Float())
    county: Mapped[str | None] = mapped_column(String(150))
    acreage: Mapped[float | None] = mapped_column(Float())
    bedrooms: Mapped[float | None] = mapped_column(Float())
    bathrooms: Mapped[float | None] = mapped_column(Float())
    square_feet: Mapped[int | None] = mapped_column(Integer())
    asking_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    annual_taxes: Mapped[float | None] = mapped_column(Numeric(14, 2))
    hoa: Mapped[float | None] = mapped_column(Numeric(14, 2))
    year_built: Mapped[int | None] = mapped_column(Integer())
    parcel_id: Mapped[str | None] = mapped_column(String(150))
    listing_status: Mapped[str | None] = mapped_column(String(100))
    pipeline_state: Mapped[dict] = mapped_column(JSON(), nullable=False, default=dict)
    provider_errors: Mapped[dict] = mapped_column(JSON(), nullable=False, default=dict)
    images: Mapped[list[str]] = mapped_column(JSON(), nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(Text())
    agent: Mapped[dict | None] = mapped_column(JSON())
    enrichment_data: Mapped[dict] = mapped_column(JSON(), nullable=False, default=dict)
    underwriting_output: Mapped[dict | None] = mapped_column(JSON())
    underwriting_assumptions: Mapped[dict | None] = mapped_column(JSON())
    overall_score: Mapped[float | None] = mapped_column(Float())
    buy_score: Mapped[float | None] = mapped_column(Float())
    airbnb_score: Mapped[float | None] = mapped_column(Float())
    wedding_score: Mapped[float | None] = mapped_column(Float())
    personal_use_score: Mapped[float | None] = mapped_column(Float())
    confidence_score: Mapped[float | None] = mapped_column(Float())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scan_history: Mapped[list["ScanHistory"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", passive_deletes=True
    )
    comparable_properties: Mapped[list["ComparableProperty"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list["PropertyDocument"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", passive_deletes=True
    )
    internal_notes: Mapped[list["PropertyNote"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", passive_deletes=True
    )
    activity_events: Mapped[list["PropertyActivityEvent"]] = relationship(back_populates="property", cascade="all, delete-orphan", passive_deletes=True)
    tasks: Mapped[list["PropertyTask"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", passive_deletes=True
    )
