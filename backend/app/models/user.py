"""
User ORM model.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserRole(str, enum.Enum):
    inspector = "inspector"
    admin = "admin"
    viewer = "viewer"
    citizen = "citizen"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"),
        nullable=False,
        default=UserRole.viewer,
    )
    xp: Mapped[int] = mapped_column(
        Integer,
        default=100,
        server_default="100",
        nullable=False,
    )
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
    inspection_histories: Mapped[list["InspectionHistory"]] = relationship(  # noqa: F821
        "InspectionHistory",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    notifications: Mapped[list["CitizenNotification"]] = relationship(  # noqa: F821
        "CitizenNotification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("xp", 100)
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"

