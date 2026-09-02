"""
Scan Pydantic schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.scan import ScanStatus, ScanType


class ScanBase(BaseModel):
    product_id: int
    scan_type: ScanType = ScanType.manual
    raw_image_url: str | None = Field(default=None, examples=["https://storage.example.com/raw.png"])


class ScanCreate(ScanBase):
    pass


class ScanUpdate(BaseModel):
    scan_type: ScanType | None = None
    raw_image_url: str | None = None
    status: ScanStatus | None = None
    processed_at: datetime | None = None


class ScanRead(ScanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ScanStatus
    processed_at: datetime | None
    created_at: datetime
