"""
Compliance Ledger Pydantic Schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CalibrationBreakdown(BaseModel):
    ar_verified: int = Field(default=0, description="Count of WebXR / AR depth-verified scans")
    reference_object: int = Field(default=0, description="Count of coin/card reference object scans")
    package_dimension: int = Field(default=0, description="Count of manual package width calibrated scans")
    dpi_estimated: int = Field(default=0, description="Count of default 300 DPI estimated scans")


class BatchStats(BaseModel):
    total_scans: int = 0
    compliant_scans: int = 0
    non_compliant_scans: int = 0
    ar_verified_count: int = 0
    reference_object_count: int = 0
    dpi_estimated_count: int = 0
    current_verdict: str = "compliant"
    last_scanned_at: str | None = None


class LedgerScanHistoryItem(BaseModel):
    scan_id: int
    scan_type: str
    status: str
    compliance_status: str
    calibration_tier: str
    batch_code: str | None = None
    violations_count: int = 0
    violations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str


class ComplianceLedgerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gtin: str
    product_name: str | None = None
    category: str | None = None
    total_scans: int
    compliant_scans: int
    non_compliant_scans: int
    current_verdict: str  # "compliant" | "non_compliant" | "disputed"
    rolling_confidence: float  # 0.0 to 1.0
    calibration_breakdown: CalibrationBreakdown
    batch_breakdown: dict[str, Any] = Field(default_factory=dict)
    last_scanned_at: datetime | None = None
    scan_history: list[LedgerScanHistoryItem] = Field(default_factory=list)


class ComplianceLedgerSummaryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gtin: str
    product_name: str | None = None
    category: str | None = None
    total_scans: int
    compliant_scans: int
    non_compliant_scans: int
    current_verdict: str
    rolling_confidence: float
    last_scanned_at: datetime | None = None
