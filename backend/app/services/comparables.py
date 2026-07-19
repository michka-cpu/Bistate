from datetime import datetime, timezone
from app.models.comparable_property import ComparableProperty
from app.models.property import Property


def collect_comparables(prop: Property) -> list[ComparableProperty]:
    """Licensed sales feeds are required; preserve no invented/sampled comparables."""
    return []


def unavailable_comparable(address: str = "Live comparable data unavailable") -> ComparableProperty:
    return ComparableProperty(address=address, source="Licensed comparable-sales feed", confidence=0, verification_status="unavailable", last_updated=datetime.now(timezone.utc))
