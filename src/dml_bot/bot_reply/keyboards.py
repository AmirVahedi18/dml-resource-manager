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
MORE_AMOUNTS = "▶ More amounts"
CONFIRM = "✅ Confirm"
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


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return _markup(
        [
            ["👤 Manage Users"],
            ["🖥 Manage Servers"],
            ["⚖️ Regulation"],
            ["📊 Usage Report"],
            ["📋 All Reservations"],
            [BACK_TO_MAIN],
        ]
    )


def paginated_list_keyboard(
    context: ContextTypes.DEFAULT_TYPE,
    items: list[tuple[str, object]],
    page: int,
    *,
    extra_rows: list[list[str]] | None = None,
) -> ReplyKeyboardMarkup:
    """`items` is (label, value) pairs for the full list; only one page's worth is shown at a
    time. Stores the choice map for the visible page's labels only."""
    start = page * PAGE_SIZE
    page_items = items[start : start + PAGE_SIZE]

    rows = [[label] for label, _ in page_items]
    for extra in extra_rows or []:
        rows.append(extra)

    page_controls = []
    if page > 0:
        page_controls.append(PREV_PAGE)
    if start + PAGE_SIZE < len(items):
        page_controls.append(NEXT_PAGE)
    if page_controls:
        rows.append(page_controls)
    rows.append(_NAV_ROW)

    store_choices(context, {label: value for label, value in page_items})
    return _markup(rows)


def action_keyboard(context: ContextTypes.DEFAULT_TYPE, actions: list[tuple[str, object]]) -> ReplyKeyboardMarkup:
    """A short, non-paginated list of action buttons (each mapped to an arbitrary value via the
    choice map) plus the nav row -- for menus with a fixed small number of options, e.g. an admin
    detail screen's toggles or the regulation field list."""
    rows = [[label] for label, _ in actions]
    rows.append(_NAV_ROW)
    store_choices(context, {label: value for label, value in actions})
    return _markup(rows)


def preset_keyboard(context: ContextTypes.DEFAULT_TYPE, presets: list[tuple[str, object]]) -> ReplyKeyboardMarkup:
    """A short, non-paginated list of preset choices plus a "More amounts" escape hatch into a
    finer-grained paginated list (see paginated_list_keyboard) -- keeps preset screens 100%
    button-driven without needing a typed "custom value" fallback."""
    rows = [[label] for label, _ in presets]
    rows.append([MORE_AMOUNTS])
    rows.append(_NAV_ROW)
    store_choices(context, {label: value for label, value in presets})
    return _markup(rows)
