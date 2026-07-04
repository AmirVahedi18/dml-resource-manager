"""Message templates and human-readable formatting for datetimes/RAM/durations."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def fmt_dt(dt: datetime, tz_name: str = "UTC") -> str:
    aware = dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))
    return aware.strftime("%Y-%m-%d %H:%M %Z")


def fmt_ram(mb: int) -> str:
    if mb >= 1024 and mb % 1024 == 0:
        return f"{mb // 1024} GB"
    return f"{mb} MB"


def fmt_duration_hours(hours: float) -> str:
    return f"{int(hours)}h" if hours == int(hours) else f"{hours:.1f}h"


def reservation_summary(reservation, gpu, server, tz_name: str = "UTC") -> str:
    duration_hours = (reservation.end_time - reservation.start_time).total_seconds() / 3600
    return (
        f"<b>Server:</b> {server.name}\n"
        f"<b>GPU:</b> {gpu.index_on_server} ({gpu.model_name})\n"
        f"<b>From:</b> {fmt_dt(reservation.start_time, tz_name)}\n"
        f"<b>To:</b> {fmt_dt(reservation.end_time, tz_name)}\n"
        f"<b>Duration:</b> {fmt_duration_hours(duration_hours)}\n"
        f"<b>RAM:</b> {fmt_ram(reservation.ram_mb)}"
    )


def watch_summary(watch, gpu, server, tz_name: str = "UTC") -> str:
    return (
        f"<b>Server:</b> {server.name}\n"
        f"<b>GPU:</b> {gpu.index_on_server} ({gpu.model_name})\n"
        f"<b>From:</b> {fmt_dt(watch.range_start, tz_name)}\n"
        f"<b>To:</b> {fmt_dt(watch.range_end, tz_name)}\n"
        f"<b>Min RAM needed:</b> {fmt_ram(watch.min_ram_needed_mb)}\n"
        f"<b>Auto-book:</b> {'yes' if watch.auto_book else 'no'}"
    )
