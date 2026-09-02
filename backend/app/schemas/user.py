"""
User Pydantic schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=150, examples=["inspector_01"])
    role: UserRole = UserRole.viewer


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, examples=["SecureP@ss1"])


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=150)
    role: UserRole | None = None
    password: str | None = Field(default=None, min_length=8)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
