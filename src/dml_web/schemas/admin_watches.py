from datetime import datetime

from pydantic import BaseModel


class AdminWatchOut(BaseModel):
    id: int
    gpu_id: int
    user_id: int
    user_full_name: str
    server_name: str
    gpu_index: int
    range_start: datetime
    range_end: datetime
    min_ram_needed_mb: int
    description: str | None
    auto_book: bool
    # "active" (still watching), "matched" (auto-booked or notified), or "cancelled".
    status: str


class AdminWatchListOut(BaseModel):
    items: list[AdminWatchOut]
    total: int
    page: int
    page_size: int
