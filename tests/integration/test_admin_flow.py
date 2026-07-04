from datetime import timedelta

from telegram.ext import ConversationHandler

from dml_bot.bot.handlers.admin import manage_regulation, manage_servers, manage_users, reservations_admin, usage_report
from dml_bot.bot.states import (
    AdminRegulationStates,
    AdminReservationsStates,
    AdminServerStates,
    AdminUsageStates,
    AdminUserStates,
)
from dml_bot.bot.handlers import common
from dml_bot.db.session import session_scope
from dml_bot.services import invite_service, regulation_service, reservation_service, server_service, user_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.telegram_helpers import FakeBot, make_callback_update, make_context, make_text_update

ADMIN_TELEGRAM_ID = 999


async def test_admin_add_user_flow_creates_invite(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_callback_update(1, ADMIN_TELEGRAM_ID, "admin:users", bot)
    state = await manage_users.start(update, context)
    assert state == AdminUserStates.MENU

    update = make_callback_update(2, ADMIN_TELEGRAM_ID, "adminusers:add", bot)
    state = await manage_users.ask_full_name(update, context)
    assert state == AdminUserStates.ADD_FULL_NAME

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "Charlie", bot)
    state = await manage_users.receive_full_name(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        invites = invite_service.list_pending_invites(session)
    assert len(invites) == 1
    assert invites[0].full_name == "Charlie"


async def test_student_redeems_invite_via_start_command(lab_setup):
    with session_scope() as session:
        invite = invite_service.create_invite(session, full_name="Charlie")
        code = invite.code

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID}, args=[code])
    update = make_text_update(1, 424242, f"/start {code}", bot)

    await common.start_command(update, context)

    with session_scope() as session:
        new_user = user_service.get_user_by_telegram_id(session, 424242)
        assert new_user is not None
        assert new_user.full_name == "Charlie"
        assert invite_service.list_pending_invites(session) == []


async def test_redeeming_unknown_code_does_not_register(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID}, args=["BADCODE1"])
    update = make_text_update(1, 424242, "/start BADCODE1", bot)

    await common.start_command(update, context)

    with session_scope() as session:
        assert user_service.get_user_by_telegram_id(session, 424242) is None
    assert "isn't valid" in bot.send_message.call_args.kwargs["text"]


async def test_redeeming_used_code_does_not_register_a_second_user(lab_setup):
    with session_scope() as session:
        invite = invite_service.create_invite(session, full_name="Charlie")
        code = invite.code
        invite_service.redeem_invite(session, code=code, telegram_id=424242)

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID}, args=[code])
    update = make_text_update(1, 111333, f"/start {code}", bot)

    await common.start_command(update, context)

    with session_scope() as session:
        assert user_service.get_user_by_telegram_id(session, 111333) is None
    assert "already been used" in bot.send_message.call_args.kwargs["text"]


async def test_non_admin_is_rejected(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_callback_update(1, lab_setup["telegram_id"], "admin:users", bot)
    state = await manage_users.start(update, context)

    assert state == ConversationHandler.END
    bot.send_message.assert_awaited_once()
    assert "Admins only" in bot.send_message.call_args.kwargs["text"]


async def test_bootstrap_admin_can_grant_and_revoke_admin_role(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    with session_scope() as session:
        user_id = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"]).id

    update = make_callback_update(1, ADMIN_TELEGRAM_ID, f"adminusers:toggleadmin:{user_id}", bot)
    state = await manage_users.toggle_admin(update, context)
    assert state == AdminUserStates.MENU

    with session_scope() as session:
        assert user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"]).is_admin is True

    update = make_callback_update(2, ADMIN_TELEGRAM_ID, f"adminusers:toggleadmin:{user_id}", bot)
    await manage_users.toggle_admin(update, context)

    with session_scope() as session:
        assert user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"]).is_admin is False


async def test_promoted_admin_cannot_toggle_admin_role(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        user_service.set_admin(session, user, True)
        user_id = user.id

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    update = make_callback_update(1, telegram_id, f"adminusers:toggleadmin:{user_id}", bot)
    state = await manage_users.toggle_admin(update, context)
    assert state == AdminUserStates.MENU

    with session_scope() as session:
        assert user_service.get_user_by_telegram_id(session, telegram_id).is_admin is True  # unchanged
    bot.answer_callback_query.assert_awaited()


async def test_admin_add_server_and_gpu_flow(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_callback_update(1, ADMIN_TELEGRAM_ID, "admin:servers", bot)
    state = await manage_servers.start(update, context)
    assert state == AdminServerStates.MENU

    update = make_callback_update(2, ADMIN_TELEGRAM_ID, "adminservers:add_server", bot)
    state = await manage_servers.ask_server_name(update, context)
    assert state == AdminServerStates.ADD_SERVER_NAME

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "lab-server-2", bot)
    state = await manage_servers.receive_server_name(update, context)
    assert state == ConversationHandler.END

    update = make_callback_update(4, ADMIN_TELEGRAM_ID, "admin:servers", bot)
    await manage_servers.start(update, context)
    update = make_callback_update(5, ADMIN_TELEGRAM_ID, "adminservers:add_gpu", bot)
    state = await manage_servers.ask_server_for_gpu(update, context)
    assert state == AdminServerStates.CHOOSE_SERVER_FOR_GPU

    with session_scope() as session:
        new_server = next(s for s in server_service.list_servers(session) if s.name == "lab-server-2")

    update = make_callback_update(6, ADMIN_TELEGRAM_ID, f"adminservers:server:{new_server.id}", bot)
    state = await manage_servers.choose_server_for_gpu(update, context)
    assert state == AdminServerStates.ADD_GPU_INDEX

    update = make_text_update(7, ADMIN_TELEGRAM_ID, "0", bot)
    state = await manage_servers.receive_gpu_index(update, context)
    assert state == AdminServerStates.ADD_GPU_MODEL

    update = make_text_update(8, ADMIN_TELEGRAM_ID, "RTX 4090", bot)
    state = await manage_servers.receive_gpu_model(update, context)
    assert state == AdminServerStates.ADD_GPU_RAM

    update = make_text_update(9, ADMIN_TELEGRAM_ID, "24576", bot)
    state = await manage_servers.receive_gpu_ram(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        new_server = next(s for s in server_service.list_servers(session) if s.name == "lab-server-2")
        gpus = server_service.list_gpus(session, new_server)
    assert len(gpus) == 1
    assert gpus[0].total_ram_mb == 24576


async def test_admin_update_regulation_flow(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_callback_update(1, ADMIN_TELEGRAM_ID, "admin:regulation", bot)
    state = await manage_regulation.start(update, context)
    assert state == AdminRegulationStates.MENU

    update = make_callback_update(2, ADMIN_TELEGRAM_ID, "adminreg:field:max_duration_hours", bot)
    state = await manage_regulation.choose_field(update, context)
    assert state == AdminRegulationStates.EDIT_VALUE

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "24", bot)
    state = await manage_regulation.receive_value(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    assert regulation.max_duration_hours == 24
    assert regulation.updated_by == ADMIN_TELEGRAM_ID


async def test_admin_usage_report_renders_chart(lab_setup):
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    # simulate a reservation that already happened: book it with a `now` override in the
    # past (so creation validation passes), leaving start/end before the real current time.
    creation_now = floor_to_slot(utc_now(), 30) - timedelta(days=2)
    start = creation_now + timedelta(hours=1)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        from dml_bot.db.models.gpu import GPU

        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation, now=creation_now)

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_callback_update(1, ADMIN_TELEGRAM_ID, "admin:usage", bot)
    state = await usage_report.start(update, context)
    assert state == AdminUsageStates.CHOOSE_SCOPE

    update = make_callback_update(2, ADMIN_TELEGRAM_ID, "adminusage:scope:user", bot)
    state = await usage_report.choose_scope(update, context)
    assert state == AdminUsageStates.CHOOSE_RANGE

    update = make_callback_update(3, ADMIN_TELEGRAM_ID, "adminusage:range:week", bot)
    state = await usage_report.choose_range(update, context)
    assert state == ConversationHandler.END

    bot.send_photo.assert_awaited_once()
    assert bot.send_photo.call_args.kwargs["photo"].startswith(b"\x89PNG")


async def test_admin_override_cancel_flow(lab_setup):
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=2)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        from dml_bot.db.models.gpu import GPU

        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation = reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation)
        reservation_id = reservation.id

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_callback_update(1, ADMIN_TELEGRAM_ID, "admin:reservations", bot)
    state = await reservations_admin.start(update, context)
    assert state == AdminReservationsStates.CHOOSE_RESERVATION

    update = make_callback_update(2, ADMIN_TELEGRAM_ID, f"adminres:choose:{reservation_id}", bot)
    state = await reservations_admin.choose_reservation(update, context)
    assert state == AdminReservationsStates.CONFIRM_CANCEL

    update = make_callback_update(3, ADMIN_TELEGRAM_ID, "adminres:confirm", bot)
    state = await reservations_admin.confirm_cancel(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        from dml_bot.db.models.reservation import Reservation, ReservationStatus

        cancelled = session.get(Reservation, reservation_id)
    assert cancelled.status == ReservationStatus.CANCELLED
