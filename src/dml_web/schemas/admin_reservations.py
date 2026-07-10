from datetime import datetime

from pydantic import BaseModel


class AdminReservationOut(BaseModel):
    id: int
    gpu_id: int
    user_id: int
    user_full_name: str
    server_name: str
    gpu_index: int
    start_time: datetime
    end_time: datetime
    ram_mb: int
    status: str


class UserWithReservationsOut(BaseModel):
    id: int
    full_name: str


class CancelAllRequest(BaseModel):
    confirm_phrase: str


class BulkCancelResult(BaseModel):
    cancelled: int
