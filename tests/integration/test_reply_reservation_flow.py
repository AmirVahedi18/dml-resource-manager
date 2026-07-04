from telegram.ext import ConversationHandler

from dml_bot.bot_reply.handlers.common import finish_admin_self_registration
from dml_bot.bot_reply.handlers.student import cancel_reservation as cancel_handlers
from dml_bot.bot_reply.handlers.student import reserve as reserve_handlers
from dml_bot.bot_reply.keyboards import BACK, CONFIRM, MAIN_MENU, NEXT_PAGE, PREV_PAGE
from dml_bot.bot_reply.states import CancelStates, ReserveStates
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, server_access_service, server_service, user_service
from tests.integration.telegram_helpers import FakeBot, make_context, make_text_update


def _first_choice_label(context) -> str:
    return next(iter(context.user_data["_choices"]))


async def test_full_reserve_flow_creates_reservation(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    update = make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot)
    state = await reserve_handlers.start(update, context)
    assert state == ReserveStates.CHOOSE_GPU

    gpu_label = _first_choice_label(context)
    update = make_text_update(2, telegram_id, gpu_label, bot)
    state = await reserve_handlers.choose_gpu(update, context)
    assert state == ReserveStates.CHOOSE_DATE

    date_label = _first_choice_label(context)
    update = make_text_update(3, telegram_id, date_label, bot)
    state = await reserve_handlers.choose_date(update, context)
    assert state == ReserveStates.CHOOSE_START_TIME

    time_label = _first_choice_label(context)
    update = make_text_update(4, telegram_id, time_label, bot)
    state = await reserve_handlers.choose_start_time(update, context)
    assert state == ReserveStates.CHOOSE_DURATION

    update = make_text_update(5, telegram_id, "2", bot)
    state = await reserve_handlers.choose_duration(update, context)
    assert state == ReserveStates.CHOOSE_RAM

    update = make_text_update(6, telegram_id, "4", bot)
    state = await reserve_handlers.choose_ram(update, context)
    assert state == ReserveStates.CONFIRM

    update = make_text_update(7, telegram_id, CONFIRM, bot)
    state = await reserve_handlers.confirm(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservations = reservation_service.list_active_reservations_for_user(session, user.id)
    assert len(reservations) == 1
    assert reservations[0].ram_mb == 4096  # "4" typed with the default GB unit


async def test_choosing_a_gpu_shows_its_availability_chart_before_the_date_step(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    update = make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot)
    await reserve_handlers.start(update, context)

    gpu_label = _first_choice_label(context)
    update = make_text_update(2, telegram_id, gpu_label, bot)
    state = await reserve_handlers.choose_gpu(update, context)
    assert state == ReserveStates.CHOOSE_DATE

    texts = [c.kwargs["text"] for c in bot.send_message.call_args_list]
    header = next(t for t in texts if "availability for the next" in t)
    assert "14 day(s)" in header  # default date_picker_days_visible
    assert any("<pre>" in t for t in texts)

    # The date step's keyboard is still the very last message sent, unaffected by the chart.
    date_markup = bot.send_message.call_args.kwargs["reply_markup"]
    assert date_markup is not None


async def test_availability_chart_renders_an_existing_reservations_occupant_name(lab_setup):
    """Regression test: the availability chart's legacy renderer reads `r.user.full_name` for
    every overlapping reservation *after* the DB session that fetched them has closed -- with no
    reservations in the window (as in the test above) that lazy load never fires, so this needs
    at least one real overlapping reservation to actually exercise it and catch a
    DetachedInstanceError."""
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    from datetime import timedelta

    from dml_bot.db.models.gpu import GPU
    from dml_bot.utils.time_utils import floor_to_slot, utc_now

    start = floor_to_slot(utc_now(), 30) + timedelta(hours=1)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        regulation = regulation_service.get_regulation(session)
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation)

    bot = FakeBot()
    context = make_context()
    update = make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot)
    await reserve_handlers.start(update, context)

    gpu_label = _first_choice_label(context)
    update = make_text_update(2, telegram_id, gpu_label, bot)
    state = await reserve_handlers.choose_gpu(update, context)
    assert state == ReserveStates.CHOOSE_DATE

    texts = [c.kwargs["text"] for c in bot.send_message.call_args_list]
    assert any("Alice" in t for t in texts)  # abbreviated occupant name rendered into the chart


async def test_reserve_unregistered_user_is_rejected(lab_setup):
    bot = FakeBot()
    context = make_context()
    update = make_text_update(1, 999999, reserve_handlers.MENU_BUTTON, bot)

    state = await reserve_handlers.start(update, context)

    assert state == ConversationHandler.END
    bot.send_message.assert_awaited_once()
    assert "not registered" in bot.send_message.call_args.kwargs["text"]


async def test_gpu_list_pagination(lab_setup):
    server_id, telegram_id = lab_setup["server_id"], lab_setup["telegram_id"]
    with session_scope() as session:
        server = session.get(Server, server_id)
        for i in range(1, 7):
            server_service.add_gpu(session, server, i, "A100", 40960)

    bot = FakeBot()
    context = make_context()

    update = make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot)
    state = await reserve_handlers.start(update, context)
    assert state == ReserveStates.CHOOSE_GPU
    assert len(context.user_data["_choices"]) == 6  # first page, PAGE_SIZE == 6

    update = make_text_update(2, telegram_id, NEXT_PAGE, bot)
    state = await reserve_handlers.choose_gpu(update, context)
    assert state == ReserveStates.CHOOSE_GPU
    assert len(context.user_data["_choices"]) == 1  # 7 GPUs total, second page has the remainder

    update = make_text_update(3, telegram_id, PREV_PAGE, bot)
    state = await reserve_handlers.choose_gpu(update, context)
    assert state == ReserveStates.CHOOSE_GPU
    assert len(context.user_data["_choices"]) == 6


async def test_date_and_start_time_steps_render_as_a_4_column_grid(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    await reserve_handlers.start(make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot), context)
    gpu_label = _first_choice_label(context)
    state = await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    assert state == ReserveStates.CHOOSE_DATE

    date_markup = bot.send_message.call_args.kwargs["reply_markup"]
    date_item_rows = date_markup.keyboard[:-1]  # exclude the Back/Main Menu nav row
    assert all(len(row) == 4 for row in date_item_rows[:-1])  # every full row has 4 columns

    date_label = _first_choice_label(context)
    state = await reserve_handlers.choose_date(make_text_update(3, telegram_id, date_label, bot), context)
    assert state == ReserveStates.CHOOSE_START_TIME

    time_markup = bot.send_message.call_args.kwargs["reply_markup"]
    time_item_rows = time_markup.keyboard[:-1]
    assert all(len(row) == 4 for row in time_item_rows[:-1])

    # the GPU list from step 1, by contrast, stays a plain one-button-per-row list
    gpu_markup = bot.send_message.call_args_list[0].kwargs["reply_markup"]
    gpu_item_rows = [row for row in gpu_markup.keyboard if len(row) == 1]
    assert len(gpu_item_rows) >= 1


async def test_cancel_reservation_flow(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    update = make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot)
    await reserve_handlers.start(update, context)
    gpu_label = _first_choice_label(context)
    await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    date_label = _first_choice_label(context)
    await reserve_handlers.choose_date(make_text_update(3, telegram_id, date_label, bot), context)
    time_label = _first_choice_label(context)
    await reserve_handlers.choose_start_time(make_text_update(4, telegram_id, time_label, bot), context)
    await reserve_handlers.choose_duration(make_text_update(5, telegram_id, "2", bot), context)
    await reserve_handlers.choose_ram(make_text_update(6, telegram_id, "4", bot), context)
    await reserve_handlers.confirm(make_text_update(7, telegram_id, CONFIRM, bot), context)

    update = make_text_update(8, telegram_id, cancel_handlers.MENU_BUTTON, bot)
    state = await cancel_handlers.start(update, context)
    assert state == CancelStates.CHOOSE_RESERVATION

    reservation_label = _first_choice_label(context)
    update = make_text_update(9, telegram_id, reservation_label, bot)
    state = await cancel_handlers.choose_reservation(update, context)
    assert state == CancelStates.CONFIRM

    update = make_text_update(10, telegram_id, CONFIRM, bot)
    state = await cancel_handlers.confirm(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservations = reservation_service.list_active_reservations_for_user(session, user.id)
    assert reservations == []


async def test_cancel_blocked_within_configured_notice_cutoff(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    await reserve_handlers.start(make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot), context)
    gpu_label = _first_choice_label(context)
    await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    date_label = _first_choice_label(context)
    await reserve_handlers.choose_date(make_text_update(3, telegram_id, date_label, bot), context)
    time_label = _first_choice_label(context)
    await reserve_handlers.choose_start_time(make_text_update(4, telegram_id, time_label, bot), context)
    await reserve_handlers.choose_duration(make_text_update(5, telegram_id, "2", bot), context)
    await reserve_handlers.choose_ram(make_text_update(6, telegram_id, "4", bot), context)
    await reserve_handlers.confirm(make_text_update(7, telegram_id, CONFIRM, bot), context)

    # An enormous notice requirement guarantees the freshly booked slot falls inside the cutoff,
    # regardless of which date/time the picker happened to offer first.
    with session_scope() as session:
        regulation_service.update_regulation(session, updated_by=1, min_cancellation_notice_minutes=10**8)

    update = make_text_update(8, telegram_id, cancel_handlers.MENU_BUTTON, bot)
    await cancel_handlers.start(update, context)
    reservation_label = _first_choice_label(context)
    await cancel_handlers.choose_reservation(make_text_update(9, telegram_id, reservation_label, bot), context)

    update = make_text_update(10, telegram_id, CONFIRM, bot)
    state = await cancel_handlers.confirm(update, context)
    assert state == ConversationHandler.END

    text = bot.send_message.call_args.kwargs["text"]
    assert "Could not cancel reservation" in text

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservations = reservation_service.list_active_reservations_for_user(session, user.id)
    assert len(reservations) == 1  # still active -- cancellation was rejected, not applied


async def test_cancel_reservation_list_label_and_confirm_screen_show_end_time_and_ram(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    update = make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot)
    await reserve_handlers.start(update, context)
    gpu_label = _first_choice_label(context)
    await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    date_label = _first_choice_label(context)
    await reserve_handlers.choose_date(make_text_update(3, telegram_id, date_label, bot), context)
    time_label = _first_choice_label(context)
    await reserve_handlers.choose_start_time(make_text_update(4, telegram_id, time_label, bot), context)
    await reserve_handlers.choose_duration(make_text_update(5, telegram_id, "2", bot), context)
    await reserve_handlers.choose_ram(make_text_update(6, telegram_id, "4", bot), context)
    await reserve_handlers.confirm(make_text_update(7, telegram_id, CONFIRM, bot), context)

    update = make_text_update(8, telegram_id, cancel_handlers.MENU_BUTTON, bot)
    await cancel_handlers.start(update, context)

    reservation_label = _first_choice_label(context)
    assert "→" in reservation_label  # start and end both present
    assert "GB" in reservation_label or "MB" in reservation_label  # RAM present

    update = make_text_update(9, telegram_id, reservation_label, bot)
    await cancel_handlers.choose_reservation(update, context)

    confirm_text = bot.send_message.call_args.kwargs["text"]
    assert "→" in confirm_text
    assert "RAM:" in confirm_text


async def test_duration_rejects_non_integer_and_out_of_range(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    await reserve_handlers.start(make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot), context)
    gpu_label = _first_choice_label(context)
    await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    date_label = _first_choice_label(context)
    await reserve_handlers.choose_date(make_text_update(3, telegram_id, date_label, bot), context)
    time_label = _first_choice_label(context)
    await reserve_handlers.choose_start_time(make_text_update(4, telegram_id, time_label, bot), context)

    # non-integer text
    state = await reserve_handlers.choose_duration(make_text_update(5, telegram_id, "two", bot), context)
    assert state == ReserveStates.CHOOSE_DURATION

    # regulation default max_duration_hours is 12 -- 999 is way over the limit
    state = await reserve_handlers.choose_duration(make_text_update(6, telegram_id, "999", bot), context)
    assert state == ReserveStates.CHOOSE_DURATION

    # zero is below the 1-hour minimum
    state = await reserve_handlers.choose_duration(make_text_update(7, telegram_id, "0", bot), context)
    assert state == ReserveStates.CHOOSE_DURATION

    # a valid whole number of hours proceeds to the RAM step
    state = await reserve_handlers.choose_duration(make_text_update(8, telegram_id, "3", bot), context)
    assert state == ReserveStates.CHOOSE_RAM
    assert context.user_data["duration_hours"] == 3


async def test_ram_rejects_non_integer_and_out_of_range(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    await reserve_handlers.start(make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot), context)
    gpu_label = _first_choice_label(context)
    await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    date_label = _first_choice_label(context)
    await reserve_handlers.choose_date(make_text_update(3, telegram_id, date_label, bot), context)
    time_label = _first_choice_label(context)
    await reserve_handlers.choose_start_time(make_text_update(4, telegram_id, time_label, bot), context)
    await reserve_handlers.choose_duration(make_text_update(5, telegram_id, "2", bot), context)

    # non-integer text
    state = await reserve_handlers.choose_ram(make_text_update(6, telegram_id, "lots", bot), context)
    assert state == ReserveStates.CHOOSE_RAM

    # the GPU has 40GB total and the regulation caps a single reservation at 16GB -- 999 is way over
    state = await reserve_handlers.choose_ram(make_text_update(7, telegram_id, "999", bot), context)
    assert state == ReserveStates.CHOOSE_RAM

    # zero is below the 1-unit minimum
    state = await reserve_handlers.choose_ram(make_text_update(8, telegram_id, "0", bot), context)
    assert state == ReserveStates.CHOOSE_RAM

    # a valid whole number of GB (the default unit) proceeds to confirmation
    state = await reserve_handlers.choose_ram(make_text_update(9, telegram_id, "8", bot), context)
    assert state == ReserveStates.CONFIRM
    assert context.user_data["ram_mb"] == 8192


async def test_ram_back_returns_to_duration_prompt(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    await reserve_handlers.start(make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot), context)
    gpu_label = _first_choice_label(context)
    await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    date_label = _first_choice_label(context)
    await reserve_handlers.choose_date(make_text_update(3, telegram_id, date_label, bot), context)
    time_label = _first_choice_label(context)
    await reserve_handlers.choose_start_time(make_text_update(4, telegram_id, time_label, bot), context)
    await reserve_handlers.choose_duration(make_text_update(5, telegram_id, "2", bot), context)

    state = await reserve_handlers.choose_ram(make_text_update(6, telegram_id, BACK, bot), context)
    assert state == ReserveStates.CHOOSE_DURATION


async def test_back_steps_one_screen_and_main_menu_exits_from_any_depth(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    state = await reserve_handlers.start(make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot), context)
    assert state == ReserveStates.CHOOSE_GPU
    gpu_label = _first_choice_label(context)
    state = await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    assert state == ReserveStates.CHOOSE_DATE

    # Back from Date goes to the previous step (GPU), not all the way to the main menu.
    state = await reserve_handlers.choose_date(make_text_update(3, telegram_id, BACK, bot), context)
    assert state == ReserveStates.CHOOSE_GPU

    # Back again, now at the very first step, exits the wizard entirely.
    state = await reserve_handlers.choose_gpu(make_text_update(4, telegram_id, BACK, bot), context)
    assert state == ConversationHandler.END

    # Main Menu exits immediately from deep in the wizard too.
    bot2 = FakeBot()
    context2 = make_context()
    await reserve_handlers.start(make_text_update(5, telegram_id, reserve_handlers.MENU_BUTTON, bot2), context2)
    gpu_label2 = _first_choice_label(context2)
    await reserve_handlers.choose_gpu(make_text_update(6, telegram_id, gpu_label2, bot2), context2)
    date_label2 = _first_choice_label(context2)
    state = await reserve_handlers.choose_date(make_text_update(7, telegram_id, date_label2, bot2), context2)
    assert state == ReserveStates.CHOOSE_START_TIME

    state = await reserve_handlers.choose_start_time(make_text_update(8, telegram_id, MAIN_MENU, bot2), context2)
    assert state == ConversationHandler.END


async def test_student_without_server_access_sees_no_gpus(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        server_access_service.set_access(session, user.id, set())  # admin revokes all access

    bot = FakeBot()
    context = make_context()
    update = make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot)
    state = await reserve_handlers.start(update, context)

    assert state == ConversationHandler.END
    bot.send_message.assert_awaited_once()
    assert "don't have access" in bot.send_message.call_args.kwargs["text"]


async def test_student_only_sees_gpus_on_granted_servers(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    with session_scope() as session:
        other_server = server_service.create_server(session, "lab-server-2")
        server_service.add_gpu(session, other_server, 0, "H100", 81920)
        # Alice keeps access to lab_setup's server only, not this new one.

    bot = FakeBot()
    context = make_context()
    update = make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot)
    state = await reserve_handlers.start(update, context)

    assert state == ReserveStates.CHOOSE_GPU
    assert len(context.user_data["_gpu_items"]) == 1  # only the originally-granted server's GPU
    assert "lab-server-1" in context.user_data["_gpu_items"][0][0]


async def test_admin_sees_all_gpus_regardless_of_access(lab_setup):
    with session_scope() as session:
        other_server = server_service.create_server(session, "lab-server-2")
        server_service.add_gpu(session, other_server, 0, "H100", 81920)
        admin_user = user_service.register_user(session, telegram_id=999, full_name="Admin")
        # no server_access rows granted to the admin at all

    bot = FakeBot()
    context = make_context(admin_ids={999})
    update = make_text_update(1, 999, reserve_handlers.MENU_BUTTON, bot)
    state = await reserve_handlers.start(update, context)

    assert state == ReserveStates.CHOOSE_GPU
    assert len(context.user_data["_gpu_items"]) == 2  # both servers' GPUs, unrestricted


async def test_unregistered_bootstrap_admin_is_prompted_for_a_name_then_can_reserve(lab_setup):
    admin_telegram_id = 4242  # in admin_ids below, but has no User row yet

    bot = FakeBot()
    context = make_context(admin_ids={admin_telegram_id})
    update = make_text_update(1, admin_telegram_id, reserve_handlers.MENU_BUTTON, bot)
    state = await reserve_handlers.start(update, context)

    assert state == ReserveStates.AWAITING_ADMIN_NAME
    prompt = bot.send_message.call_args.kwargs["text"]
    assert "name" in prompt.lower()

    update = make_text_update(2, admin_telegram_id, "Dr. Admin", bot)
    state = await finish_admin_self_registration(
        update, context, ReserveStates.AWAITING_ADMIN_NAME, reserve_handlers.start
    )

    # Registration succeeded and the reserve flow resumed straight into GPU selection.
    assert state == ReserveStates.CHOOSE_GPU
    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, admin_telegram_id)
    assert user is not None
    assert user.full_name == "Dr. Admin"
