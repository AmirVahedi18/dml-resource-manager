from pydantic import BaseModel


class RegulationUpdateRequest(BaseModel):
    max_ram_per_reservation_gb: int
    max_duration_hours: int
    booking_horizon_days: int
    min_reservation_slot_minutes: int
    max_active_reservations_per_user: int
    min_cancellation_notice_minutes: int
