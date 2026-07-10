from datetime import datetime

from pydantic import BaseModel


class WatchCreate(BaseModel):
    gpu_id: int
    range_start: datetime
    range_end: datetime
    min_ram_needed_mb: int


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
