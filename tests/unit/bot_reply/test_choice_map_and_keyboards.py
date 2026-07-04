from types import SimpleNamespace

from dml_bot.bot_reply.choice_map import resolve_choice, store_choices
from dml_bot.bot_reply.keyboards import (
    BACK,
    BACK_TO_MAIN,
    DONE,
    MAIN_MENU,
    NEXT_PAGE,
    PREV_PAGE,
    admin_menu_keyboard,
    paginated_list_keyboard,
    toggle_list_keyboard,
)
from dml_bot.bot_reply.presets import ram_unit_mb


def _context():
    return SimpleNamespace(user_data={})


def test_choice_map_round_trip():
    context = _context()
    store_choices(context, {"Alice": 1, "Bob": 2})
    assert resolve_choice(context, "Alice") == 1
    assert resolve_choice(context, "Bob") == 2
    assert resolve_choice(context, "Charlie") is None


def test_paginated_list_keyboard_first_page_has_only_next():
    context = _context()
    items = [(f"item{i}", i) for i in range(10)]
    markup = paginated_list_keyboard(context, items, page=0)

    button_texts = [btn.text for row in markup.keyboard for btn in row]
    assert PREV_PAGE not in button_texts
    assert NEXT_PAGE in button_texts
    assert BACK in button_texts
    assert MAIN_MENU in button_texts
    assert resolve_choice(context, "item0") == 0
    assert resolve_choice(context, "item9") is None  # not on this page


def test_paginated_list_keyboard_last_page_has_only_prev():
    context = _context()
    items = [(f"item{i}", i) for i in range(10)]
    markup = paginated_list_keyboard(context, items, page=1)

    button_texts = [btn.text for row in markup.keyboard for btn in row]
    assert PREV_PAGE in button_texts
    assert NEXT_PAGE not in button_texts
    assert resolve_choice(context, "item9") == 9


def test_paginated_list_keyboard_grid_layout_chunks_rows_by_columns():
    context = _context()
    items = [(f"item{i}", i) for i in range(24)]
    markup = paginated_list_keyboard(context, items, page=0, columns=4, rows=6)

    item_rows = markup.keyboard[:-1]  # last row is the nav row (Back / Main Menu)
    assert all(len(row) == 4 for row in item_rows)
    assert len(item_rows) == 6
    assert [btn.text for btn in item_rows[0]] == ["item0", "item1", "item2", "item3"]
    assert resolve_choice(context, "item23") == 23


def test_paginated_list_keyboard_grid_still_paginates_when_over_page_size():
    context = _context()
    items = [(f"item{i}", i) for i in range(30)]
    markup = paginated_list_keyboard(context, items, page=0, columns=4, rows=6)  # page_size=24

    button_texts = [btn.text for row in markup.keyboard for btn in row]
    assert NEXT_PAGE in button_texts
    assert resolve_choice(context, "item23") == 23
    assert resolve_choice(context, "item24") is None  # on the next page


def test_toggle_list_keyboard_shows_checked_and_unchecked_state():
    context = _context()
    markup = toggle_list_keyboard(context, [("Server A", 1), ("Server B", 2)], selected={1})

    button_texts = [btn.text for row in markup.keyboard for btn in row]
    assert "✅ Server A" in button_texts
    assert "⬜ Server B" in button_texts
    assert DONE in button_texts
    assert BACK in button_texts
    assert resolve_choice(context, "✅ Server A") == 1
    assert resolve_choice(context, "⬜ Server B") == 2


def test_ram_unit_mb():
    assert ram_unit_mb("GB") == 1024
    assert ram_unit_mb("gb") == 1024
    assert ram_unit_mb("MB") == 1
    assert ram_unit_mb("mb") == 1


def test_admin_menu_keyboard_renders_as_a_3_column_grid_with_back_row_separate():
    markup = admin_menu_keyboard(columns=3)

    item_rows = markup.keyboard[:-1]
    assert [btn.text for row in item_rows for btn in row] == [
        "👤 Manage Users",
        "🖥 Manage Servers",
        "⚖️ Regulation",
        "📊 Usage Report",
        "📋 All Reservations",
        "🎨 Chart Style",
    ]
    assert len(item_rows[0]) == 3
    assert len(item_rows[1]) == 3
    assert [btn.text for btn in markup.keyboard[-1]] == [BACK_TO_MAIN]
