"""Fixed-width monospace RAM-occupancy bar chart for a GPU's schedule.

Renders one line per fixed-size time bucket, bar length proportional to RAM used
(not time), so overlapping reservations on the same GPU show as partial fills
rather than a single busy/free block. Every bucket is shown (including fully
free ones) at the exact configured `bucket_hours`, regardless of how long the
selected range is -- no merging, no auto-widening. Every line (bucket or day
header) is capped at `max_width_chars` and never wraps: occupant names are
abbreviated (e.g. "Ali Ahmadi" -> "A.Ahmadi") and truncated with an ellipsis if
they still don't fit, rather than spilling onto a second line.

Because a long range at a small bucket size can produce more text than fits in
one Telegram message (4096-char hard limit), `render_ram_chart` returns a list
of already-paginated page strings -- the caller sends each as its own message.
Pages only ever split between two calendar days, never in the middle of one.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

_MIN_BAR_CHARS = 4
_NAME_FIELD_TARGET = 10
_MESSAGE_CHAR_BUDGET = 3500  # safety margin under Telegram's 4096-char hard limit


@dataclass
class _Bucket:
    start_local: datetime
    end_local: datetime
    used_mb: int
    names: list[str]


def _to_local(dt_utc_naive: datetime, tz_name: str) -> datetime:
    return dt_utc_naive.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))


def _to_utc_naive(dt_local_aware: datetime) -> datetime:
    return dt_local_aware.astimezone(timezone.utc).replace(tzinfo=None)


def _bucket_boundaries(range_start: datetime, range_end: datetime, tz_name: str, bucket_hours: float) -> list[datetime]:
    """Local-time bucket edges, anchored to local midnight so labels read like a clock."""
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


def _covers_single_day(start_local: datetime, end_local: datetime) -> bool:
    end_date = end_local.date() - timedelta(days=1) if end_local.time() == time(0, 0) else end_local.date()
    return end_date == start_local.date()


def _time_label(start_local: datetime, end_local: datetime) -> str:
    if _covers_single_day(start_local, end_local):
        def fmt(dt: datetime, hour_override: int | None = None) -> str:
            hour = hour_override if hour_override is not None else dt.hour
            return f"{hour:02d}:{dt.minute:02d}" if dt.minute else f"{hour:02d}"

        end_hour_override = 24 if end_local.date() != start_local.date() else None
        return f"{fmt(start_local)}-{fmt(end_local, end_hour_override)}"

    last_day = end_local.date() - timedelta(days=1) if end_local.time() == time(0, 0) else end_local.date()
    return f"{start_local.strftime('%b%d')}–{last_day.strftime('%b%d')}"


def _display_unit(cap_mb: int) -> tuple[str, int]:
    if cap_mb >= 1024:
        return "GB", 1024
    return "MB", 1


def _abbrev_name(full_name: str) -> str:
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0][0]}.{parts[-1]}"


def _paginate_lines(lines: list[str], budget: int) -> list[str]:
    """Greedy line-by-line packing, with no regard for day boundaries -- only used as a fallback
    when a single day's lines alone already exceed the budget (see _paginate_groups)."""
    pages: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        add_len = len(line) + 1
        if current and current_len + add_len > budget:
            pages.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += add_len
    if current:
        pages.append("\n".join(current))
    return pages


def _paginate_groups(groups: list[list[str]], budget: int = _MESSAGE_CHAR_BUDGET) -> list[str]:
    """Packs whole day-groups (day header + its bucket lines) into pages, only ever splitting
    between two days -- never in the middle of a day -- so a message break always lands on a new
    calendar day. Falls back to a mid-day split only if a single day's lines alone don't fit in
    one message."""
    pages: list[str] = []
    current: list[str] = []
    current_len = 0
    for group in groups:
        group_len = sum(len(line) + 1 for line in group)

        if group_len > budget:
            if current:
                pages.append("\n".join(current))
                current, current_len = [], 0
            pages.extend(_paginate_lines(group, budget))
            continue

        if current and current_len + group_len > budget:
            pages.append("\n".join(current))
            current, current_len = [], 0
        current.extend(group)
        current_len += group_len

    if current:
        pages.append("\n".join(current))
    return pages


def render_ram_chart(
    reservations: list,
    cap_mb: int,
    range_start: datetime,
    range_end: datetime,
    tz_name: str,
    bucket_hours: float,
    max_width_chars: int,
) -> list[str]:
    """HTML-escaped chart pages, each meant to be wrapped in its own Telegram <pre> block."""
    cap_mb = max(cap_mb, 1)
    bucket_hours = max(bucket_hours, 0.25)  # guard against a misconfigured <=0 value looping forever
    boundaries = _bucket_boundaries(range_start, range_end, tz_name, bucket_hours)

    buckets: list[_Bucket] = []
    for start_local, end_local in zip(boundaries, boundaries[1:]):
        b_start_utc = _to_utc_naive(start_local)
        b_end_utc = _to_utc_naive(end_local)
        overlapping = [r for r in reservations if r.start_time < b_end_utc and r.end_time > b_start_utc]
        overlapping.sort(key=lambda r: r.start_time)
        used_mb = sum(r.ram_mb for r in overlapping)
        names = list(dict.fromkeys(r.user.full_name for r in overlapping))  # de-dup, keep order
        buckets.append(_Bucket(start_local, end_local, used_mb, names))

    unit_label, divisor = _display_unit(cap_mb)
    cap_val = max(round(cap_mb / divisor), 1)
    frac_width = 2 * len(str(cap_val)) + 1

    labels = [_time_label(b.start_local, b.end_local) for b in buckets]
    label_width = max((len(label) for label in labels), default=5)

    total_avail = max(max_width_chars - label_width - frac_width - 3, _MIN_BAR_CHARS)
    # Split any width beyond the bar/name minimums proportionally, so the name field also
    # grows (not just the bar) when max_width_chars leaves more room to work with.
    leftover = max(total_avail - _MIN_BAR_CHARS - _NAME_FIELD_TARGET, 0)
    bar_width = max(_MIN_BAR_CHARS + round(leftover * 0.6), _MIN_BAR_CHARS)
    bar_width = min(bar_width, total_avail)
    name_field_width = max(total_avail - bar_width, 0)

    groups: list[list[str]] = []
    current_day = None
    for bucket, label in zip(buckets, labels):
        if bucket.start_local.date() != current_day:
            current_day = bucket.start_local.date()
            groups.append([bucket.start_local.strftime("%a %b %d")])

        used_val = min(round(bucket.used_mb / divisor), cap_val)
        fill = min(round((bucket.used_mb / cap_mb) * bar_width), bar_width) if bucket.used_mb else 0
        bar = "█" * fill + "░" * (bar_width - fill)
        frac = f"{used_val:>{len(str(cap_val))}}/{cap_val}"
        line = f"{label:<{label_width}} {bar} {frac}"

        if bucket.names and name_field_width > 0:
            names_str = ",".join(_abbrev_name(html.escape(n)) for n in bucket.names)
            if len(names_str) > name_field_width:
                names_str = names_str[: max(name_field_width - 1, 0)] + "…"
            line += f" {names_str}"

        groups[-1].append(line)

    pages = _paginate_groups(groups)
    if not pages:
        pages = [""]

    title = f"{unit_label} used · {bucket_hours:g}h/bar"
    n_pages = len(pages)
    return [
        (f"{title} ({i + 1}/{n_pages})\n" if n_pages > 1 else f"{title}\n") + page
        for i, page in enumerate(pages)
    ]
