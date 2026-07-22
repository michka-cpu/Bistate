from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ComparableProperty(Base):
    """A comparable property associated with a tracked property."""

    __tablename__ = "comparable_properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    square_feet: Mapped[int | None]
    property_type: Mapped[str | None] = mapped_column(String(100))
    bedrooms: Mapped[float | None] = mapped_column(Float())
    bathrooms: Mapped[float | None] = mapped_column(Float())
    acreage: Mapped[float | None] = mapped_column(Float())
    distance_miles: Mapped[float | None] = mapped_column(Float())
    sale_date: Mapped[date | None] = mapped_column(Date())
    price_per_square_foot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="Unavailable")
    confidence: Mapped[float] = mapped_column(Float(), nullable=False, default=0)
    similarity_score: Mapped[float | None] = mapped_column(Float())
    adjustments: Mapped[list[dict]] = mapped_column(JSON(), nullable=False, default=list)
    provenance: Mapped[dict] = mapped_column(JSON(), nullable=False, default=dict)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unavailable")
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())

    property: Mapped["Property"] = relationship(back_populates="comparable_properties")
