from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Patient(BaseModel):
    id: str | None = None
    name: str | None = None
    phone: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
