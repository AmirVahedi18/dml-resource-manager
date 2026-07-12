from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ReservationCreate(BaseModel):
    gpu_id: int
    start_time: datetime
    end_time: datetime
    ram_mb: int
    description: str = Field(min_length=1, max_length=300)

    @field_validator("description")
    @classmethod
    def _strip_and_require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("description must not be blank")
        return stripped


# Student-facing -- deliberately omits `description`. Only admins can read what a reservation is
# for (see AdminReservationOut); a student's own list/detail views never expose it.
class ReservationOut(BaseModel):
    id: int
    gpu_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    ram_mb: int
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}
