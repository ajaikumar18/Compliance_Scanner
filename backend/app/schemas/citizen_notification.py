"""
Citizen Notification Pydantic schemas.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CitizenNotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    scan_id: int | None = None
    notification_type: str
    title: str
    message: str
    xp_change: int
    is_read: bool
    created_at: datetime
