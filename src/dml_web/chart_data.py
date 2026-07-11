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


def _peak_usage_breakdown(
    entries: list[tuple[datetime, datetime, str, int]], bucket_start: datetime, bucket_end: datetime
) -> dict[str, int]:
    """Per-user RAM held at the single busiest instant inside [bucket_start, bucket_end).

    Naively summing every reservation's full ram_mb whenever it merely overlaps the bucket
    overcounts: two reservations that each cover only part of the bucket -- say one ends 10
    minutes in and another starts an hour later -- were never actually concurrent, so adding
    their full ram_mb together can push a bucket's total well past the GPU's real capacity. This
    instead sweeps start/end events and snapshots the per-user breakdown at the instant total
    concurrent usage peaks, which by construction can never exceed capacity."""
    events: list[tuple[datetime, str, int]] = []
    for start, end, user, ram_mb in entries:
        cs, ce = max(start, bucket_start), min(end, bucket_end)
        if cs >= ce:
            continue
        events.append((cs, user, ram_mb))
        events.append((ce, user, -ram_mb))
    if not events:
        return {}
    events.sort(key=lambda e: e[0])

    current: dict[str, int] = {}
    total = 0
    best_total = -1
    best_snapshot: dict[str, int] = {}
    for _, user, delta in events:
        current[user] = current.get(user, 0) + delta
        if current[user] <= 0:
            del current[user]
        total += delta
        if total > best_total:
            best_total = total
            best_snapshot = dict(current)
    return best_snapshot


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

    occupied = []
    for r in reservations:
        window = _occupied_window(r)
        if window:
            occupied.append((window[0], window[1], r.user.full_name, r.ram_mb))

    boundaries = _bucket_boundaries(range_start, range_end, tz_name, bucket_hours)
    buckets = []
    for start_local, end_local in zip(boundaries, boundaries[1:]):
        b_start_utc, b_end_utc = _to_utc_naive(start_local), _to_utc_naive(end_local)
        entries = [e for e in occupied if e[0] < b_end_utc and e[1] > b_start_utc]
        usage = _peak_usage_breakdown(entries, b_start_utc, b_end_utc)
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
