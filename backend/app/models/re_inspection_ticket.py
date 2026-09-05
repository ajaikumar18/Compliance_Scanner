"""
Re-Inspection Ticket ORM Model.
Tracks discrepancies where a new scan conflicts with the compliance ledger consensus
(e.g., sensor tier escalation like AR over DPI, or verdict flip from compliant to non-compliant).
"""

from __future__ import annotations

from datetime import datetime
import enum
from typing import Any

from sqlalchemy import DateTime, Double, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TicketPriority(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TicketStatus(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"
    dismissed = "dismissed"


class ConflictType(str, enum.Enum):
    sensor_tier_escalation = "sensor_tier_escalation"
    verdict_inversion = "verdict_inversion"
    consensus_disputed = "consensus_disputed"
    confidence_drop = "confidence_drop"


class ReInspectionTicket(Base):
    __tablename__ = "re_inspection_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    gtin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    batch_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # The triggering scan that caused the conflict
    trigger_scan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Discrepancy Snapshot
    prior_verdict: Mapped[str] = mapped_column(String(30), nullable=False)  # "compliant" | "non_compliant" | "disputed"
    prior_confidence: Mapped[float] = mapped_column(Double, nullable=False)
    prior_calibration_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "dpi_estimated" etc.

    new_verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    new_confidence: Mapped[float] = mapped_column(Double, nullable=False)
    new_calibration_tier: Mapped[str] = mapped_column(String(50), nullable=False)

    conflict_type: Mapped[str] = mapped_column(String(50), nullable=False, default="verdict_inversion")
    discrepancy_reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Prioritization and Queue Management
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open", index=True)

    assigned_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to the trigger scan
    trigger_scan: Mapped["Scan | None"] = relationship("Scan", lazy="selectin")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<ReInspectionTicket {self.ticket_number} gtin={self.gtin} "
            f"priority={self.priority} status={self.status}>"
        )
