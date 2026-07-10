"""SQLite drops tzinfo on round-trip, so the app stores/compares all datetimes as naive UTC."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_EPOCH = datetime(1970, 1, 1)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def is_slot_aligned(dt: datetime, slot_minutes: int) -> bool:
    seconds_since_epoch = (to_naive_utc(dt) - _EPOCH).total_seconds()
    return int(seconds_since_epoch) % (slot_minutes * 60) == 0


def floor_to_slot(dt: datetime, slot_minutes: int) -> datetime:
    """Round `dt` (naive UTC) up to the next slot boundary."""
    seconds_since_epoch = (dt - _EPOCH).total_seconds()
    remainder = int(seconds_since_epoch) % (slot_minutes * 60)
    return dt if remainder == 0 else dt + timedelta(seconds=slot_minutes * 60 - remainder)


def align_down_to_slot(dt: datetime, slot_minutes: int) -> datetime:
    """Round `dt` (naive UTC) down to the previous slot boundary."""
    seconds_since_epoch = (dt - _EPOCH).total_seconds()
    remainder = int(seconds_since_epoch) % (slot_minutes * 60)
    return dt - timedelta(seconds=remainder)


def local_day_range_utc(local_date: date, tz_name: str) -> tuple[datetime, datetime]:
    start_local = datetime(local_date.year, local_date.month, local_date.day, tzinfo=ZoneInfo(tz_name))
    return to_naive_utc(start_local), to_naive_utc(start_local + timedelta(days=1))


def generate_slot_starts(
    range_start: datetime, range_end: datetime, slot_minutes: int, not_before: datetime
) -> list[datetime]:
    """UTC slot-aligned start times within [range_start, range_end), never earlier than `not_before`."""
    t = floor_to_slot(max(range_start, not_before), slot_minutes)
    slots = []
    while t < range_end:
        slots.append(t)
        t += timedelta(minutes=slot_minutes)
    return slots


def to_local_label(utc_dt: datetime, tz_name: str, fmt: str = "%H:%M") -> str:
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name)).strftime(fmt)
