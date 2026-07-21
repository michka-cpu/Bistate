from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DiscoveredListing(Base):
    """A search result kept outside the underwriting property pipeline until analyzed."""

    __tablename__ = "discovered_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_listing_id: Mapped[str] = mapped_column(String(255), nullable=False)
    listing_source: Mapped[str] = mapped_column(String(100), nullable=False)
    listing_url: Mapped[str | None] = mapped_column(String(2000))
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20))
    county: Mapped[str | None] = mapped_column(String(150))
    asking_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    acreage: Mapped[float | None] = mapped_column(Float())
    bedrooms: Mapped[float | None] = mapped_column(Float())
    bathrooms: Mapped[float | None] = mapped_column(Float())
    property_type: Mapped[str | None] = mapped_column(String(100))
    photo_url: Mapped[str | None] = mapped_column(String(2000))
    listing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_watchlisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
