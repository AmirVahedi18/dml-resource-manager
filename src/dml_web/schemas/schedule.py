from pydantic import BaseModel


class ServerOut(BaseModel):
    id: int
    name: str
    description: str | None
    model_config = {"from_attributes": True}


class GpuOut(BaseModel):
    id: int
    server_id: int
    index_on_server: int
    model_name: str
    total_ram_mb: int
    model_config = {"from_attributes": True}


class RegulationOut(BaseModel):
    max_ram_per_reservation_mb: int
    max_duration_hours: int
    booking_horizon_days: int
    min_reservation_slot_minutes: int
    max_active_reservations_per_user: int
    min_cancellation_notice_minutes: int
    # Not a Regulation column: filled in by the /api/regulation route from app_cfg.bot.timezone.
    # The frontend must build reservation start/end times against this timezone (not the
    # visiting browser's), since slot alignment is checked in UTC and the two only agree if
    # times are picked relative to the app's single configured timezone.
    timezone: str = "UTC"
    model_config = {"from_attributes": True}
