"""
Compliance Ledger ORM model.
Tracks aggregate compliance status, sensor counts, and rolling confidence by GTIN.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Double, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ComplianceLedger(Base):
    __tablename__ = "compliance_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    gtin: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Aggregated Scan Counts
    total_scans: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compliant_scans: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    non_compliant_scans: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Calibration Sensor Breakdown Counts
    ar_verified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reference_object_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    package_dimension_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dpi_estimated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Current Aggregate Verdict: "compliant", "non_compliant", "disputed"
    current_verdict: Mapped[str] = mapped_column(String(30), nullable=False, default="compliant", index=True)

    # Rolling Confidence Score (0.0 to 1.0)
    rolling_confidence: Mapped[float] = mapped_column(Double, nullable=False, default=1.0)

    # Per-Batch Stats Breakdown: { batch_code: { total_scans, compliant_scans, verdict, ... } }
    batch_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Pointer to most recent scan
    last_scan_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scans.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    last_scan: Mapped["Scan | None"] = relationship("Scan", lazy="selectin")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ComplianceLedger gtin={self.gtin} verdict={self.current_verdict} scans={self.total_scans} conf={self.rolling_confidence:.2f}>"
