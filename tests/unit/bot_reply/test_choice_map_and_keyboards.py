from types import SimpleNamespace

from dml_bot.bot_reply.choice_map import resolve_choice, store_choices
from dml_bot.bot_reply.keyboards import BACK, MAIN_MENU, MORE_AMOUNTS, NEXT_PAGE, PREV_PAGE, paginated_list_keyboard, preset_keyboard
from dml_bot.bot_reply.presets import fine_ram_options


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


def test_preset_keyboard_includes_more_amounts_and_nav_row():
    context = _context()
    markup = preset_keyboard(context, [("1h", 1.0), ("2h", 2.0)])
    button_texts = [btn.text for row in markup.keyboard for btn in row]
    assert MORE_AMOUNTS in button_texts
    assert BACK in button_texts
    assert MAIN_MENU in button_texts
    assert resolve_choice(context, "1h") == 1.0


def test_fine_ram_options_includes_cap_even_if_not_a_multiple():
    options = fine_ram_options(5000, step_mb=1024)
    values = [v for _, v in options]
    assert values[-1] == 5000
    assert 4096 in values
