from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Float, ForeignKey, Numeric, String, func
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
    distance_miles: Mapped[float | None] = mapped_column(Float())
    sale_date: Mapped[date | None] = mapped_column(Date())
    price_per_square_foot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="Unavailable")
    confidence: Mapped[float] = mapped_column(Float(), nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unavailable")
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acreage: Mapped[float | None] = mapped_column(Float())
    bedrooms: Mapped[float | None] = mapped_column(Float())
    bathrooms: Mapped[float | None] = mapped_column(Float())
    year_built: Mapped[int | None]
    latitude: Mapped[float | None] = mapped_column(Float())
    longitude: Mapped[float | None] = mapped_column(Float())
    price_per_acre: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    similarity_score: Mapped[float | None] = mapped_column(Float())

    property: Mapped["Property"] = relationship(back_populates="comparable_properties")
