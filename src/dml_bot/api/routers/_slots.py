from datetime import date as date_cls
from datetime import timedelta

from sqlalchemy.orm import Session

from dml_bot.db.models.gpu import GPU
from dml_bot.services import regulation_service, reservation_service
from dml_bot.utils.time_utils import local_day_range_utc, to_local_label


def build_day_slots(session: Session, gpu: GPU, day: date_cls, tz_name: str) -> list[dict]:
    regulation = regulation_service.get_regulation(session)
    range_start, range_end = local_day_range_utc(day, tz_name)
    raw_slots = reservation_service.slot_availability(
        session, gpu, range_start, range_end, regulation.min_reservation_slot_minutes
    )

    slots = []
    for slot_start, free_mb in raw_slots:
        slot_end = slot_start + timedelta(minutes=regulation.min_reservation_slot_minutes)
        slots.append(
            {
                "start": slot_start.isoformat(),
                "end": slot_end.isoformat(),
                "label": to_local_label(slot_start, tz_name),
                "label_end": to_local_label(slot_end, tz_name),
                "free_mb": free_mb,
            }
        )
    return slots
