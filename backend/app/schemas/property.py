from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PropertyBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=20)
    notes: str | None = None


class PropertyCreate(PropertyBase):
    pass


class PropertyRead(PropertyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
