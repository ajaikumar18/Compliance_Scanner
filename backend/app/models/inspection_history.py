"""
InspectionHistory ORM model.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class InspectionHistory(Base):
    __tablename__ = "inspection_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="inspection_histories",
        lazy="selectin",
    )
    scan: Mapped["Scan"] = relationship(  # noqa: F821
        "Scan",
        back_populates="inspection_histories",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<InspectionHistory id={self.id} user_id={self.user_id} "
            f"scan_id={self.scan_id} action={self.action!r}>"
        )
