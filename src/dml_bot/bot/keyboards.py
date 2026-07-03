"""Inline keyboard builders. Every wizard is a sequence of one-screen button menus."""
from datetime import date, datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CANCEL_BUTTON = InlineKeyboardButton("❌ Cancel", callback_data="wizard:cancel")
BACK_TO_MAIN_BUTTON = InlineKeyboardButton("⬅️ Back", callback_data="menu:main")


def main_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001f4c5 Reserve GPU", callback_data="menu:reserve")],
        [InlineKeyboardButton("\U0001f5c2 My Reservations", callback_data="menu:my_reservations")],
        [InlineKeyboardButton("\U0001f4ca View Schedule", callback_data="menu:schedule")],
        [InlineKeyboardButton("\U0001f514 My Watches", callback_data="menu:watches")],
        [InlineKeyboardButton("❓ Help", callback_data="menu:help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("\U0001f6e0 Admin Panel", callback_data="menu:admin")])
    return InlineKeyboardMarkup(rows)


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001f464 Manage Users", callback_data="admin:users")],
        [InlineKeyboardButton("\U0001f5a5 Manage Servers", callback_data="admin:servers")],
        [InlineKeyboardButton("⚖️ Regulation", callback_data="admin:regulation")],
        [InlineKeyboardButton("\U0001f4ca Usage Report", callback_data="admin:usage")],
        [InlineKeyboardButton("\U0001f4cb All Reservations", callback_data="admin:reservations")],
        [BACK_TO_MAIN_BUTTON],
    ]
    return InlineKeyboardMarkup(rows)


def cancel_only_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[CANCEL_BUTTON]])


def server_list_keyboard(servers, prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(s.name, callback_data=f"{prefix}:server:{s.id}")] for s in servers]
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(rows)


def gpu_list_keyboard(gpus, prefix: str) -> InlineKeyboardMarkup:
    rows = []
    for g in gpus:
        label = f"GPU {g.index_on_server} · {g.model_name} · {g.total_ram_mb}MB"
        rows.append([InlineKeyboardButton(label, callback_data=f"{prefix}:gpu:{g.id}")])
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(rows)


def date_picker_keyboard(start_date: date, days_visible: int, prefix: str) -> InlineKeyboardMarkup:
    rows, row = [], []
    for i in range(days_visible):
        d = start_date + timedelta(days=i)
        row.append(InlineKeyboardButton(d.strftime("%a %d %b"), callback_data=f"{prefix}:date:{d.isoformat()}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(rows)


def time_picker_keyboard(slots: list[tuple[str, datetime]], prefix: str) -> InlineKeyboardMarkup:
    """`slots` is (label, utc_datetime) pairs; label is the time shown to the user (their local tz)."""
    rows, row = [], []
    for label, utc_dt in slots:
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}:time:{utc_dt.isoformat()}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(rows)


def duration_keyboard(preset_hours: list[float], prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"{h}h", callback_data=f"{prefix}:duration:{h}")] for h in preset_hours]
    rows.append([InlineKeyboardButton("✏️ Custom (type hours)", callback_data=f"{prefix}:duration:custom")])
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(rows)


def ram_keyboard(preset_mb: list[int], prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"{mb} MB", callback_data=f"{prefix}:ram:{mb}")] for mb in preset_mb]
    rows.append([InlineKeyboardButton("✏️ Custom (type MB)", callback_data=f"{prefix}:ram:custom")])
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(rows)


def confirm_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Confirm", callback_data=f"{prefix}:confirm")],
            [CANCEL_BUTTON],
        ]
    )


def item_list_keyboard(items: list[tuple[int, str]], prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"{prefix}:{item_id}")] for item_id, label in items]
    rows.append([BACK_TO_MAIN_BUTTON])
    return InlineKeyboardMarkup(rows)


def yes_no_keyboard(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Yes", callback_data=yes_data), InlineKeyboardButton("❌ No", callback_data=no_data)]]
    )


def range_picker_keyboard(prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Today", callback_data=f"{prefix}:range:today")],
        [InlineKeyboardButton("This week", callback_data=f"{prefix}:range:week")],
        [InlineKeyboardButton("Next 30 days", callback_data=f"{prefix}:range:month")],
        [InlineKeyboardButton("Full booking horizon", callback_data=f"{prefix}:range:horizon")],
        [CANCEL_BUTTON],
    ]
    return InlineKeyboardMarkup(rows)


def past_range_picker_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Same range keys as range_picker_keyboard, but labelled for backward-looking usage reports."""
    rows = [
        [InlineKeyboardButton("Today", callback_data=f"{prefix}:range:today")],
        [InlineKeyboardButton("Past week", callback_data=f"{prefix}:range:week")],
        [InlineKeyboardButton("Past 30 days", callback_data=f"{prefix}:range:month")],
        [InlineKeyboardButton("Full booking horizon", callback_data=f"{prefix}:range:horizon")],
        [CANCEL_BUTTON],
    ]
    return InlineKeyboardMarkup(rows)
