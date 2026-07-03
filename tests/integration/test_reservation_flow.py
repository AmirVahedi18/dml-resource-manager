from datetime import date, timedelta

from telegram.ext import ConversationHandler

from dml_bot.bot.handlers.student import reserve as reserve_handlers
from dml_bot.bot.states import ReserveStates
from dml_bot.db.session import session_scope
from dml_bot.services import reservation_service, user_service
from tests.integration.telegram_helpers import FakeBot, make_callback_update, make_context


async def test_full_reserve_flow_creates_reservation(lab_setup):
    server_id, gpu_id, telegram_id = lab_setup["server_id"], lab_setup["gpu_id"], lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    update = make_callback_update(1, telegram_id, "menu:reserve", bot)
    state = await reserve_handlers.start(update, context)
    assert state == ReserveStates.CHOOSE_SERVER

    update = make_callback_update(2, telegram_id, f"reserve:server:{server_id}", bot)
    state = await reserve_handlers.choose_server(update, context)
    assert state == ReserveStates.CHOOSE_GPU

    update = make_callback_update(3, telegram_id, f"reserve:gpu:{gpu_id}", bot)
    state = await reserve_handlers.choose_gpu(update, context)
    assert state == ReserveStates.CHOOSE_DATE

    target_date = (date.today() + timedelta(days=1)).isoformat()
    update = make_callback_update(4, telegram_id, f"reserve:date:{target_date}", bot)
    state = await reserve_handlers.choose_date(update, context)
    assert state == ReserveStates.CHOOSE_START_TIME

    markup = bot.edit_message_text.call_args.kwargs["reply_markup"]
    first_time_cb = markup.inline_keyboard[0][0].callback_data
    chosen_time_iso = first_time_cb.split(":", 2)[2]

    update = make_callback_update(5, telegram_id, f"reserve:time:{chosen_time_iso}", bot)
    state = await reserve_handlers.choose_start_time(update, context)
    assert state == ReserveStates.CHOOSE_DURATION

    update = make_callback_update(6, telegram_id, "reserve:duration:2", bot)
    state = await reserve_handlers.choose_duration(update, context)
    assert state == ReserveStates.CHOOSE_RAM

    update = make_callback_update(7, telegram_id, "reserve:ram:4096", bot)
    state = await reserve_handlers.choose_ram(update, context)
    assert state == ReserveStates.CONFIRM

    update = make_callback_update(8, telegram_id, "reserve:confirm", bot)
    state = await reserve_handlers.confirm(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservations = reservation_service.list_active_reservations_for_user(session, user.id)
    assert len(reservations) == 1
    assert reservations[0].ram_mb == 4096


async def test_reserve_unregistered_user_is_rejected(lab_setup):
    bot = FakeBot()
    context = make_context()
    update = make_callback_update(1, 999999, "menu:reserve", bot)

    state = await reserve_handlers.start(update, context)

    assert state == ConversationHandler.END
    bot.edit_message_text.assert_awaited_once()
    assert "not registered" in bot.edit_message_text.call_args.kwargs["text"]
