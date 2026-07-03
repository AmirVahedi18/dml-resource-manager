from telegram.ext import ConversationHandler

from dml_bot.bot_reply.handlers.student import cancel_reservation as cancel_handlers
from dml_bot.bot_reply.handlers.student import reserve as reserve_handlers
from dml_bot.bot_reply.keyboards import BACK, CONFIRM, MAIN_MENU, NEXT_PAGE, PREV_PAGE
from dml_bot.bot_reply.states import CancelStates, ReserveStates
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import reservation_service, server_service, user_service
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

    ram_label = _first_choice_label(context)
    update = make_text_update(6, telegram_id, ram_label, bot)
    state = await reserve_handlers.choose_ram(update, context)
    assert state == ReserveStates.CONFIRM

    update = make_text_update(7, telegram_id, CONFIRM, bot)
    state = await reserve_handlers.confirm(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservations = reservation_service.list_active_reservations_for_user(session, user.id)
    assert len(reservations) == 1


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
    ram_label = _first_choice_label(context)
    await reserve_handlers.choose_ram(make_text_update(6, telegram_id, ram_label, bot), context)
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
