from datetime import datetime

from pydantic import BaseModel


class ReservationCreate(BaseModel):
    gpu_id: int
    start_time: datetime
    end_time: datetime
    ram_mb: int


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
