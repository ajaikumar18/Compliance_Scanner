"""
Scan ORM model.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ScanType(str, enum.Enum):
    manual = "manual"
    batch = "batch"
    ecommerce = "ecommerce"


class ScanStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_type: Mapped[ScanType] = mapped_column(
        Enum(ScanType, name="scantype"),
        nullable=False,
        default=ScanType.manual,
    )
    raw_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scanstatus"),
        nullable=False,
        default=ScanStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship(  # noqa: F821
        "Product",
        back_populates="scans",
        lazy="selectin",
    )
    violations: Mapped[list["Violation"]] = relationship(  # noqa: F821
        "Violation",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    inspection_histories: Mapped[list["InspectionHistory"]] = relationship(  # noqa: F821
        "InspectionHistory",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Scan id={self.id} product_id={self.product_id} type={self.scan_type} status={self.status}>"
