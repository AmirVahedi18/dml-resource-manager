from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    message: str
    created_at: datetime
    model_config = {"from_attributes": True}
