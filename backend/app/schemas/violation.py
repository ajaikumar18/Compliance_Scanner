"""
Violation Pydantic schemas.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.violation import ViolationSeverity, ViolationType


class ViolationBase(BaseModel):
    scan_id: int
    field_name: str = Field(..., min_length=1, max_length=200, examples=["net_weight"])
    violation_type: ViolationType
    details: str | None = Field(default=None, examples=["Expected format: 'XXX g', got 'XXXg'"])
    severity: ViolationSeverity = ViolationSeverity.medium


class ViolationCreate(ViolationBase):
    pass


class ViolationRead(ViolationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
