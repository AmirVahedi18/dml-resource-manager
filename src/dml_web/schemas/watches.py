from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WatchCreate(BaseModel):
    gpu_id: int
    range_start: datetime
    range_end: datetime
    min_ram_needed_mb: int
    description: str = Field(min_length=1, max_length=300)

    @field_validator("description")
    @classmethod
    def _strip_and_require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("description must not be blank")
        return stripped


# Student-facing -- deliberately omits `description`, same as ReservationOut: a watch's
# description is only ever readable once (by admins) after it turns into a reservation.
class WatchOut(BaseModel):
    id: int
    gpu_id: int
    range_start: datetime
    range_end: datetime
    min_ram_needed_mb: int
    auto_book: bool
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}
