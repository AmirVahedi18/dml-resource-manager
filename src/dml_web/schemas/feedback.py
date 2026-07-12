from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from dml_core.db.models.feedback import FeedbackCategory


class FeedbackCreate(BaseModel):
    category: FeedbackCategory
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def _strip_and_require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


# A student's own submitted feedback -- visible to them (so they know what they reported), never
# to other students. Admins see every user's feedback via AdminFeedbackOut instead.
class FeedbackOut(BaseModel):
    id: int
    category: FeedbackCategory
    message: str
    created_at: datetime
    model_config = {"from_attributes": True}
