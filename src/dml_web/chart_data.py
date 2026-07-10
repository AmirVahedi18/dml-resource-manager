"""Pure JSON-shaping for the SPA's occupancy/usage charts. Deliberately independent from
`bot_reply/ram_chart*.py` (Telegram-only text/PNG rendering, which stays untouched) -- a small
amount of bucket-boundary math is duplicated here in exchange for the web backend never reaching
into bot-interface modules. See the "Charts" section of the web-interface plan for the rationale.

The SPA gets one payload per GPU/range covering both a bucketed view (stacked bar) and an exact-
boundary view (area/timeline), so switching chart style client-side needs no second request.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dml_bot.db.models.reservation import Reservation


def _to_local(dt_utc_naive: datetime, tz_name: str) -> datetime:
    return dt_utc_naive.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))


def _to_utc_naive(dt_local_aware: datetime) -> datetime:
    return dt_local_aware.astimezone(timezone.utc).replace(tzinfo=None)


def _bucket_boundaries(
    range_start: datetime, range_end: datetime, tz_name: str, bucket_hours: float
) -> list[datetime]:
    """Local-time bucket edges, anchored to local midnight so buckets read like a clock."""
    step = timedelta(hours=bucket_hours)
    start_local = _to_local(range_start, tz_name)
    end_local = _to_local(range_end, tz_name)
    day_start = start_local.replace(hour=0, minute=0, second=0, microsecond=0)
    offset_steps = int((start_local - day_start) // step)
    t = day_start + offset_steps * step

    boundaries = [t]
    while t < end_local:
        t += step
        boundaries.append(t)
    return boundaries


def historical_bucket_hours(days: int) -> float:
    """Scales an admin-chosen historical window's bucket size so a multi-month lookback doesn't
    render as thousands of buckets (reservations are kept forever -- see scheduling/jobs.py's
    run_cleanup on the bot side, which this mirrors the intent of, not the code, of)."""
    if days <= 2:
        return 1.0
    if days <= 7:
        return 3.0
    if days <= 30:
        return 12.0
    if days <= 120:
        return 24.0
    return 24.0 * 7


def build_occupancy_chart(
    reservations: list[Reservation],
    capacity_mb: int,
    range_start: datetime,
    range_end: datetime,
    tz_name: str,
    bucket_hours: float,
) -> dict:
    capacity_mb = max(capacity_mb, 1)
    bucket_hours = max(bucket_hours, 0.25)

    boundaries = _bucket_boundaries(range_start, range_end, tz_name, bucket_hours)
    buckets = []
    for start_local, end_local in zip(boundaries, boundaries[1:]):
        b_start_utc, b_end_utc = _to_utc_naive(start_local), _to_utc_naive(end_local)
        usage: dict[str, int] = {}
        for r in reservations:
            if r.start_time < b_end_utc and r.end_time > b_start_utc:
                usage[r.user.full_name] = usage.get(r.user.full_name, 0) + r.ram_mb
        buckets.append({"start": start_local.isoformat(), "end": end_local.isoformat(), "usage": usage})

    segments = [
        {
            "start": _to_local(r.start_time, tz_name).isoformat(),
            "end": _to_local(r.end_time, tz_name).isoformat(),
            "user": r.user.full_name,
            "ram_mb": r.ram_mb,
            "reservation_id": r.id,
        }
        for r in sorted(reservations, key=lambda r: r.start_time)
    ]

    return {
        "range_start": _to_local(range_start, tz_name).isoformat(),
        "range_end": _to_local(range_end, tz_name).isoformat(),
        "capacity_mb": capacity_mb,
        "tz": tz_name,
        "bucket_hours": bucket_hours,
        "buckets": buckets,
        "segments": segments,
    }
