"""
Re-Inspection Ticket Pydantic Schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReInspectionTicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    gtin: str
    product_name: str | None = None
    batch_code: str | None = None
    trigger_scan_id: int

    prior_verdict: str
    prior_confidence: float
    prior_calibration_tier: str | None = None

    new_verdict: str
    new_confidence: float
    new_calibration_tier: str

    conflict_type: str
    discrepancy_reason: str

    priority: str  # "critical" | "high" | "medium" | "low"
    status: str    # "open" | "investigating" | "resolved" | "dismissed"

    assigned_to: str | None = None
    resolution_notes: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Optional nested trigger scan details
    trigger_scan_violations: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "inspector"
    claimed_violation_type: str | None = None


class ReInspectionTicketUpdate(BaseModel):
    status: str | None = Field(default=None, description="New status: open, investigating, resolved, dismissed")
    assigned_to: str | None = Field(default=None, description="Officer assigned to investigate")
    resolution_notes: str | None = Field(default=None, description="Resolution or investigation findings")


class TicketSummaryStats(BaseModel):
    total_tickets: int = 0
    open_tickets: int = 0
    critical_tickets: int = 0
    high_tickets: int = 0
    investigating_tickets: int = 0
    resolved_tickets: int = 0
