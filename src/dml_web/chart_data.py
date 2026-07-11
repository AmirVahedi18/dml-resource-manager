"""Pure JSON-shaping for the SPA's occupancy/usage charts.

The SPA gets one payload per GPU/range covering both a bucketed view (stacked bar) and an exact-
boundary view (area/timeline), so switching chart style client-side needs no second request.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dml_core.db.models.reservation import Reservation


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


def historical_bucket_hours(days: int, base_hours: float) -> float:
    """Scales an admin-chosen historical window's bucket size so a multi-month lookback doesn't
    render as thousands of buckets (reservations are kept forever, never pruned by cleanup).

    Windows up to a week use `base_hours` unscaled, matching the live schedule view's bucket
    size (`schedule_chart.bucket_hours`) so the two charts read the same way for the same range.
    """
    if days <= 7:
        return base_hours
    if days <= 30:
        return max(base_hours, 12.0)
    if days <= 120:
        return max(base_hours, 24.0)
    return max(base_hours, 24.0 * 7)


def _occupied_window(r: Reservation) -> tuple[datetime, datetime] | None:
    """A reservation's actual occupancy window. For a cancelled reservation this ends at
    `cancelled_at` instead of the originally-booked `end_time`, so historical charts (which
    include cancelled reservations for an accurate record) don't show GPU time as occupied past
    the point it was actually freed up. Returns None if it never occupied the GPU at all (e.g.
    cancelled before its window started)."""
    end = r.end_time if r.cancelled_at is None else min(r.end_time, r.cancelled_at)
    if end <= r.start_time:
        return None
    return r.start_time, end


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
            window = _occupied_window(r)
            if window and window[0] < b_end_utc and window[1] > b_start_utc:
                usage[r.user.full_name] = usage.get(r.user.full_name, 0) + r.ram_mb
        buckets.append({"start": start_local.isoformat(), "end": end_local.isoformat(), "usage": usage})

    segments = [
        {
            "start": _to_local(r.start_time, tz_name).isoformat(),
            "end": _to_local(r.end_time, tz_name).isoformat(),
            "user": r.user.full_name,
            "ram_mb": r.ram_mb,
            "reservation_id": r.id,
            "cancelled": r.cancelled_at is not None,
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
