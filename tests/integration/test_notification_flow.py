from datetime import timedelta

from telegram.ext import ConversationHandler

from dml_bot.bot.handlers.student import cancel_reservation as cancel_handlers
from dml_bot.bot.states import CancelStates
from dml_bot.db.models.gpu import GPU
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, user_service, watch_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.telegram_helpers import FakeBot, make_callback_update, make_context


async def test_cancelling_a_reservation_frees_capacity_for_a_watcher(lab_setup):
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=8)
    end = start + timedelta(hours=2)

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.update_regulation(
            session, updated_by=555, max_ram_per_reservation_mb=gpu.total_ram_mb
        )
        occupier = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation = reservation_service.create_reservation(
            session, occupier, gpu, start, end, gpu.total_ram_mb, regulation
        )
        reservation_id = reservation.id

        watcher = user_service.register_user(session, telegram_id=777, full_name="Bob")
        watch_service.create_watch(session, watcher, gpu, start, end, 1000)

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        assert watch_service.find_matching_watches(session, gpu) == []

    bot = FakeBot()
    context = make_context()
    update = make_callback_update(1, telegram_id, "menu:my_reservations", bot)
    state = await cancel_handlers.start(update, context)
    assert state == CancelStates.CHOOSE_RESERVATION

    update = make_callback_update(2, telegram_id, f"cancelres:choose:{reservation_id}", bot)
    state = await cancel_handlers.choose_reservation(update, context)
    assert state == CancelStates.CONFIRM

    update = make_callback_update(3, telegram_id, "cancelres:confirm", bot)
    state = await cancel_handlers.confirm(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        matches = watch_service.find_matching_watches(session, gpu)
    assert len(matches) == 1
    assert matches[0].min_ram_needed_mb == 1000
