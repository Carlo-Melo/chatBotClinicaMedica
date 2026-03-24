from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AppointmentStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class AppointmentRequest(BaseModel):
    id: str | None = None
    patient_id: str | None = None
    patient_name: str | None = None
    phone: str
    doctor: str
    requested_date: str
    requested_date_iso: datetime | None = None
    notes: str | None = None
    status: AppointmentStatus = AppointmentStatus.PENDING
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
