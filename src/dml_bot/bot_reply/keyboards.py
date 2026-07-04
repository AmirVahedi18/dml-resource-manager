"""ReplyKeyboardMarkup builders. Every screen is a persistent, flat button grid docked below the
message box; list-selection screens also populate the choice map (see choice_map.py) since a
reply-keyboard press carries no hidden id, only its visible label.
"""
from telegram import ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from dml_bot.bot_reply.choice_map import store_choices

BACK = "◀ Back"
MAIN_MENU = "🏠 Main Menu"
BACK_TO_MAIN = "⬅️ Back to menu"
PREV_PAGE = "◀ Prev"
NEXT_PAGE = "Next ▶"
CONFIRM = "✅ Confirm"
DONE = "✅ Done"
HELP = "❓ Help"
ADMIN_PANEL = "🛠 Admin Panel"

PAGE_SIZE = 6

# Every wizard screen ends with this row: Back steps back one screen (or exits on the first
# screen of a wizard), Main Menu exits the wizard immediately from anywhere.
_NAV_ROW = [BACK, MAIN_MENU]


def _markup(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def cancel_only_keyboard() -> ReplyKeyboardMarkup:
    return _markup([_NAV_ROW])


def confirm_keyboard() -> ReplyKeyboardMarkup:
    return _markup([[CONFIRM], _NAV_ROW])


def main_menu_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [
        ["📅 Reserve GPU", "🗂 My Reservations", "🗓 Schedule"],
        ["🔔 Watches", HELP],
    ]
    if is_admin:
        rows.append([ADMIN_PANEL])
    return _markup(rows)


def admin_menu_keyboard(columns: int = 1) -> ReplyKeyboardMarkup:
    items = ["👤 Manage Users", "🖥 Manage Servers", "⚖️ Regulation", "📊 Usage Report", "📋 All Reservations"]
    item_rows = [items[i : i + columns] for i in range(0, len(items), columns)]
    return _markup([*item_rows, [BACK_TO_MAIN]])


def paginated_list_keyboard(
    context: ContextTypes.DEFAULT_TYPE,
    items: list[tuple[str, object]],
    page: int,
    *,
    extra_rows: list[list[str]] | None = None,
    columns: int = 1,
    rows: int = PAGE_SIZE,
) -> ReplyKeyboardMarkup:
    """`items` is (label, value) pairs for the full list; only one page's worth (`columns * rows`
    items) is shown at a time, laid out `columns`-wide per row -- `columns=1` (the default) is the
    original one-button-per-row layout; screens with many short labels (start times, dates, ...)
    pass a larger `columns` to fit more per screen without wasting vertical space. Stores the
    choice map for the visible page's labels only."""
    page_size = columns * rows
    start = page * page_size
    page_items = items[start : start + page_size]

    button_rows = [
        [label for label, _ in page_items[i : i + columns]] for i in range(0, len(page_items), columns)
    ]
    for extra in extra_rows or []:
        button_rows.append(extra)

    page_controls = []
    if page > 0:
        page_controls.append(PREV_PAGE)
    if start + page_size < len(items):
        page_controls.append(NEXT_PAGE)
    if page_controls:
        button_rows.append(page_controls)
    button_rows.append(_NAV_ROW)

    store_choices(context, {label: value for label, value in page_items})
    return _markup(button_rows)


def action_keyboard(context: ContextTypes.DEFAULT_TYPE, actions: list[tuple[str, object]]) -> ReplyKeyboardMarkup:
    """A short, non-paginated list of action buttons (each mapped to an arbitrary value via the
    choice map) plus the nav row -- for menus with a fixed small number of options, e.g. an admin
    detail screen's toggles or the regulation field list."""
    rows = [[label] for label, _ in actions]
    rows.append(_NAV_ROW)
    store_choices(context, {label: value for label, value in actions})
    return _markup(rows)


def toggle_list_keyboard(
    context: ContextTypes.DEFAULT_TYPE, items: list[tuple[str, object]], selected: set
) -> ReplyKeyboardMarkup:
    """A fixed list of checkbox-style toggle buttons (each label prefixed with its ✅/⬜ state)
    plus a Done button -- for "pick any number of these" screens like a student's server-access
    grants. Each press re-renders this same screen with the toggle flipped; Done finalizes."""
    rows = []
    choice_map = {}
    for label, value in items:
        mark = "✅" if value in selected else "⬜"
        button_label = f"{mark} {label}"
        rows.append([button_label])
        choice_map[button_label] = value
    rows.append([DONE])
    rows.append(_NAV_ROW)
    store_choices(context, choice_map)
    return _markup(rows)
