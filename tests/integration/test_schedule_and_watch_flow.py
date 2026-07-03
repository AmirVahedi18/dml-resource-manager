from datetime import timedelta

from telegram.ext import ConversationHandler

from dml_bot.bot.handlers.student import view_schedule as schedule_handlers
from dml_bot.bot.handlers.student import watch as watch_handlers
from dml_bot.bot.states import ScheduleStates, WatchFlowStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.session import session_scope
from dml_bot.services import reservation_service, user_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.telegram_helpers import FakeBot, make_callback_update, make_context, make_text_update


async def test_view_schedule_shows_existing_reservation(lab_setup):
    server_id, gpu_id, telegram_id = lab_setup["server_id"], lab_setup["gpu_id"], lab_setup["telegram_id"]
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=8)
    end = start + timedelta(hours=2)

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        from dml_bot.services import regulation_service

        regulation = regulation_service.get_regulation(session)
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation)

    bot = FakeBot()
    context = make_context()

    update = make_callback_update(1, telegram_id, "menu:schedule", bot)
    state = await schedule_handlers.start(update, context)
    assert state == ScheduleStates.CHOOSE_SERVER

    update = make_callback_update(2, telegram_id, f"schedule:server:{server_id}", bot)
    state = await schedule_handlers.choose_server(update, context)
    assert state == ScheduleStates.CHOOSE_GPU

    update = make_callback_update(3, telegram_id, f"schedule:gpu:{gpu_id}", bot)
    state = await schedule_handlers.choose_gpu(update, context)
    assert state == ScheduleStates.CHOOSE_RANGE

    update = make_callback_update(4, telegram_id, "schedule:range:week", bot)
    state = await schedule_handlers.choose_range(update, context)
    assert state == ConversationHandler.END

    shown_text = bot.edit_message_text.call_args.kwargs["text"]
    assert "Alice" in shown_text
    assert "4096" in shown_text or "4 GB" in shown_text


async def test_watch_created_then_listed_and_cancelled(lab_setup):
    server_id, gpu_id, telegram_id = lab_setup["server_id"], lab_setup["gpu_id"], lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    update = make_callback_update(1, telegram_id, "menu:watches", bot)
    state = await watch_handlers.start(update, context)
    assert state == WatchFlowStates.MENU

    update = make_callback_update(2, telegram_id, "watch:new", bot)
    state = await watch_handlers.new_watch(update, context)
    assert state == WatchFlowStates.CHOOSE_SERVER

    update = make_callback_update(3, telegram_id, f"watch:server:{server_id}", bot)
    state = await watch_handlers.choose_server(update, context)
    assert state == WatchFlowStates.CHOOSE_GPU

    update = make_callback_update(4, telegram_id, f"watch:gpu:{gpu_id}", bot)
    state = await watch_handlers.choose_gpu(update, context)
    assert state == WatchFlowStates.CHOOSE_RANGE

    update = make_callback_update(5, telegram_id, "watch:range:week", bot)
    state = await watch_handlers.choose_range(update, context)
    assert state == WatchFlowStates.CHOOSE_RAM

    update = make_text_update(6, telegram_id, "2048", bot)
    state = await watch_handlers.choose_ram(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        from dml_bot.services import watch_service

        watches = watch_service.list_watches_for_user(session, user.id)
    assert len(watches) == 1
    watch_id = watches[0].id

    update = make_callback_update(7, telegram_id, "menu:watches", bot)
    state = await watch_handlers.start(update, context)
    assert state == WatchFlowStates.MENU

    update = make_callback_update(8, telegram_id, f"watchlist:choose:{watch_id}", bot)
    state = await watch_handlers.choose_existing(update, context)
    assert state == WatchFlowStates.CONFIRM_CANCEL

    update = make_callback_update(9, telegram_id, "watchlist:confirm", bot)
    state = await watch_handlers.confirm_cancel(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        from dml_bot.services import watch_service

        user = user_service.get_user_by_telegram_id(session, telegram_id)
        assert watch_service.list_watches_for_user(session, user.id) == []
