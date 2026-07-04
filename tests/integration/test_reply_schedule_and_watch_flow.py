from datetime import timedelta

from telegram.ext import ConversationHandler

from dml_bot.bot_reply.handlers.student import view_schedule as schedule_handlers
from dml_bot.bot_reply.handlers.student import watch as watch_handlers
from dml_bot.bot_reply.keyboards import CONFIRM
from dml_bot.bot_reply.states import ScheduleStates, WatchFlowStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, user_service, watch_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.telegram_helpers import FakeBot, make_context, make_text_update


def _first_choice_label(context) -> str:
    return next(iter(context.user_data["_choices"]))


async def test_view_schedule_shows_existing_reservation(lab_setup):
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=8)
    end = start + timedelta(hours=2)

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        regulation = regulation_service.get_regulation(session)
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation)

    bot = FakeBot()
    context = make_context()

    update = make_text_update(1, telegram_id, schedule_handlers.MENU_BUTTON, bot)
    state = await schedule_handlers.start(update, context)
    assert state == ScheduleStates.CHOOSE_GPU

    gpu_label = _first_choice_label(context)
    update = make_text_update(2, telegram_id, gpu_label, bot)
    state = await schedule_handlers.choose_gpu(update, context)
    assert state == ScheduleStates.CHOOSE_RANGE

    update = make_text_update(3, telegram_id, "7 days", bot)
    state = await schedule_handlers.choose_range(update, context)
    assert state == ConversationHandler.END

    sent_texts = [call.kwargs["text"] for call in bot.send_message.call_args_list]
    exact_list_text = next(t for t in sent_texts if "→" in t)  # the exact per-reservation list
    assert "Alice" in exact_list_text
    assert "4096" in exact_list_text or "4 GB" in exact_list_text


async def test_watch_created_then_listed_and_cancelled(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    update = make_text_update(1, telegram_id, watch_handlers.MENU_BUTTON, bot)
    state = await watch_handlers.start(update, context)
    assert state == WatchFlowStates.MENU

    update = make_text_update(2, telegram_id, watch_handlers.NEW_WATCH, bot)
    state = await watch_handlers.menu_choice(update, context)
    assert state == WatchFlowStates.CHOOSE_GPU

    gpu_label = _first_choice_label(context)
    update = make_text_update(3, telegram_id, gpu_label, bot)
    state = await watch_handlers.choose_gpu(update, context)
    assert state == WatchFlowStates.CHOOSE_RANGE

    update = make_text_update(4, telegram_id, "This week", bot)
    state = await watch_handlers.choose_range(update, context)
    assert state == WatchFlowStates.CHOOSE_RAM

    update = make_text_update(5, telegram_id, "2", bot)
    state = await watch_handlers.choose_ram(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        watches = watch_service.list_watches_for_user(session, user.id)
    assert len(watches) == 1
    assert watches[0].min_ram_needed_mb == 2048

    update = make_text_update(6, telegram_id, watch_handlers.MENU_BUTTON, bot)
    state = await watch_handlers.start(update, context)
    assert state == WatchFlowStates.MENU

    watch_label = _first_choice_label(context)
    update = make_text_update(7, telegram_id, watch_label, bot)
    state = await watch_handlers.menu_choice(update, context)
    assert state == WatchFlowStates.CONFIRM_CANCEL

    update = make_text_update(8, telegram_id, CONFIRM, bot)
    state = await watch_handlers.confirm_cancel(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        assert watch_service.list_watches_for_user(session, user.id) == []


async def test_watch_ram_rejects_non_integer_and_out_of_range(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    await watch_handlers.start(make_text_update(1, telegram_id, watch_handlers.MENU_BUTTON, bot), context)
    await watch_handlers.menu_choice(make_text_update(2, telegram_id, watch_handlers.NEW_WATCH, bot), context)
    gpu_label = _first_choice_label(context)
    await watch_handlers.choose_gpu(make_text_update(3, telegram_id, gpu_label, bot), context)
    await watch_handlers.choose_range(make_text_update(4, telegram_id, "This week", bot), context)

    # non-integer text
    state = await watch_handlers.choose_ram(make_text_update(5, telegram_id, "lots", bot), context)
    assert state == WatchFlowStates.CHOOSE_RAM

    # the GPU has 40GB total -- 999 is way over
    state = await watch_handlers.choose_ram(make_text_update(6, telegram_id, "999", bot), context)
    assert state == WatchFlowStates.CHOOSE_RAM

    # zero is below the 1-unit minimum
    state = await watch_handlers.choose_ram(make_text_update(7, telegram_id, "0", bot), context)
    assert state == WatchFlowStates.CHOOSE_RAM
