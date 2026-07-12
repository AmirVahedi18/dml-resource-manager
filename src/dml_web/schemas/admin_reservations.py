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
    description: str | None
    status: str


class AdminReservationListOut(BaseModel):
    items: list[AdminReservationOut]
    total: int
    page: int
    page_size: int


class CancelAllRequest(BaseModel):
    confirm_phrase: str


class BulkCancelResult(BaseModel):
    cancelled: int
