"""
InspectionHistory Pydantic schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InspectionHistoryBase(BaseModel):
    user_id: int
    scan_id: int
    action: str = Field(..., min_length=1, max_length=255, examples=["scan_reviewed"])


class InspectionHistoryCreate(InspectionHistoryBase):
    pass


class InspectionHistoryRead(InspectionHistoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
