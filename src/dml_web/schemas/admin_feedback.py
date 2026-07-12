from datetime import datetime

from pydantic import BaseModel

from dml_core.db.models.feedback import FeedbackCategory


class AdminFeedbackOut(BaseModel):
    id: int
    user_id: int
    user_full_name: str
    category: FeedbackCategory
    message: str
    created_at: datetime


class AdminFeedbackListOut(BaseModel):
    items: list[AdminFeedbackOut]
    total: int
    page: int
    page_size: int
