"""
Citizen Notification ORM model.
"""

from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class NotificationType(str, enum.Enum):
    violation_confirmed = "violation_confirmed"
    claim_refuted = "claim_refuted"
    tampering_detected = "tampering_detected"
    ticket_resolved = "ticket_resolved"
    ticket_dismissed = "ticket_dismissed"
    system_notice = "system_notice"


class CitizenNotification(Base):
    __tablename__ = "citizen_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notificationtype"),
        nullable=False,
        default=NotificationType.system_notice,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    xp_change: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="notifications",
        lazy="selectin",
    )
    scan: Mapped["Scan | None"] = relationship(  # noqa: F821
        "Scan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<CitizenNotification id={self.id} user_id={self.user_id} title={self.title!r} xp_change={self.xp_change}>"
