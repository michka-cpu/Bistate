from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
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

    property: Mapped["Property"] = relationship(back_populates="comparable_properties")
