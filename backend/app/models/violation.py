"""
Violation ORM model.
"""

import enum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ViolationType(str, enum.Enum):
    missing = "missing"
    incorrect_format = "incorrect_format"
    undersized_font = "undersized_font"


class ViolationSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(200), nullable=False)
    violation_type: Mapped[ViolationType] = mapped_column(
        Enum(ViolationType, name="violationtype"),
        nullable=False,
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[ViolationSeverity] = mapped_column(
        Enum(ViolationSeverity, name="violationseverity"),
        nullable=False,
        default=ViolationSeverity.medium,
    )

    # Relationships
    scan: Mapped["Scan"] = relationship(  # noqa: F821
        "Scan",
        back_populates="violations",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Violation id={self.id} scan_id={self.scan_id} "
            f"field={self.field_name!r} type={self.violation_type} severity={self.severity}>"
        )
