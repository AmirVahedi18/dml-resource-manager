from datetime import timedelta

from telegram.ext import ConversationHandler

from dml_bot.bot_reply.handlers.admin import (
    manage_regulation,
    manage_servers,
    manage_users,
    reservations_admin,
    usage_report,
)
from dml_bot.bot_reply.keyboards import BACK, CONFIRM, MAIN_MENU
from dml_bot.bot_reply.states import (
    AdminRegulationStates,
    AdminReservationsStates,
    AdminServerStates,
    AdminUsageStates,
    AdminUserStates,
)
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import regulation_service, reservation_service, server_service, user_service
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.telegram_helpers import FakeBot, make_context, make_text_update

ADMIN_TELEGRAM_ID = 999


def _first_choice_label(context) -> str:
    return next(iter(context.user_data["_choices"]))


async def test_admin_add_user_flow(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot)
    state = await manage_users.start(update, context)
    assert state == AdminUserStates.MENU

    update = make_text_update(2, ADMIN_TELEGRAM_ID, manage_users.ADD_USER, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.ADD_TELEGRAM_ID

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "424242", bot)
    state = await manage_users.receive_telegram_id(update, context)
    assert state == AdminUserStates.ADD_FULL_NAME

    update = make_text_update(4, ADMIN_TELEGRAM_ID, "Charlie", bot)
    state = await manage_users.receive_full_name(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        new_user = user_service.get_user_by_telegram_id(session, 424242)
    assert new_user is not None
    assert new_user.full_name == "Charlie"


async def test_non_admin_is_rejected(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, lab_setup["telegram_id"], manage_users.MENU_BUTTON, bot)
    state = await manage_users.start(update, context)

    assert state == ConversationHandler.END
    bot.send_message.assert_awaited_once()
    assert "Admins only" in bot.send_message.call_args.kwargs["text"]


async def test_admin_toggle_active_and_privilege(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot)
    await manage_users.start(update, context)
    alice_label = next(label for label in context.user_data["_choices"] if label.startswith("Alice"))

    update = make_text_update(2, ADMIN_TELEGRAM_ID, alice_label, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.MENU

    toggle_label = next(
        label for label, val in context.user_data["_choices"].items() if isinstance(val, tuple) and val[0] == "toggle_active"
    )
    update = make_text_update(3, ADMIN_TELEGRAM_ID, toggle_label, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.MENU

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
    assert user.is_active is False


async def test_admin_add_server_and_gpu_flow(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_servers.MENU_BUTTON, bot)
    state = await manage_servers.start(update, context)
    assert state == AdminServerStates.MENU

    update = make_text_update(2, ADMIN_TELEGRAM_ID, "➕ Add Server", bot)
    state = await manage_servers.menu_choice(update, context)
    assert state == AdminServerStates.ADD_SERVER_NAME

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "lab-server-2", bot)
    state = await manage_servers.receive_server_name(update, context)
    assert state == ConversationHandler.END

    update = make_text_update(4, ADMIN_TELEGRAM_ID, manage_servers.MENU_BUTTON, bot)
    await manage_servers.start(update, context)
    update = make_text_update(5, ADMIN_TELEGRAM_ID, "➕ Add GPU", bot)
    state = await manage_servers.menu_choice(update, context)
    assert state == AdminServerStates.CHOOSE_SERVER_FOR_GPU

    assert "lab-server-2" in context.user_data["_choices"]
    update = make_text_update(6, ADMIN_TELEGRAM_ID, "lab-server-2", bot)
    state = await manage_servers.choose_server_for_gpu(update, context)
    assert state == AdminServerStates.ADD_GPU_INDEX

    update = make_text_update(7, ADMIN_TELEGRAM_ID, "0", bot)
    state = await manage_servers.receive_gpu_index(update, context)
    assert state == AdminServerStates.ADD_GPU_MODEL

    update = make_text_update(8, ADMIN_TELEGRAM_ID, "RTX 4090", bot)
    state = await manage_servers.receive_gpu_model(update, context)
    assert state == AdminServerStates.ADD_GPU_RAM

    assert "24 GB" in context.user_data["_choices"]
    update = make_text_update(9, ADMIN_TELEGRAM_ID, "24 GB", bot)
    state = await manage_servers.choose_gpu_ram(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        new_server = next(s for s in server_service.list_servers(session) if s.name == "lab-server-2")
        gpus = server_service.list_gpus(session, new_server)
    assert len(gpus) == 1
    assert gpus[0].total_ram_mb == 24576


async def test_admin_add_gpu_custom_ram(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_servers.MENU_BUTTON, bot)
    await manage_servers.start(update, context)
    update = make_text_update(2, ADMIN_TELEGRAM_ID, "➕ Add GPU", bot)
    await manage_servers.menu_choice(update, context)

    server_label = _first_choice_label(context)
    update = make_text_update(3, ADMIN_TELEGRAM_ID, server_label, bot)
    await manage_servers.choose_server_for_gpu(update, context)
    update = make_text_update(4, ADMIN_TELEGRAM_ID, "1", bot)
    await manage_servers.receive_gpu_index(update, context)
    update = make_text_update(5, ADMIN_TELEGRAM_ID, "NVIDIA H100", bot)
    state = await manage_servers.receive_gpu_model(update, context)
    assert state == AdminServerStates.ADD_GPU_RAM

    update = make_text_update(6, ADMIN_TELEGRAM_ID, manage_servers.GPU_RAM_OTHER, bot)
    state = await manage_servers.choose_gpu_ram(update, context)
    assert state == AdminServerStates.ADD_GPU_RAM_CUSTOM

    update = make_text_update(7, ADMIN_TELEGRAM_ID, "102400", bot)
    state = await manage_servers.receive_gpu_ram_custom(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        all_gpus = []
        for s in server_service.list_servers(session):
            all_gpus.extend(server_service.list_gpus(session, s))
        matching = [g for g in all_gpus if g.model_name == "NVIDIA H100"]
    assert len(matching) == 1
    assert matching[0].total_ram_mb == 102400


async def test_admin_update_regulation_flow(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_regulation.MENU_BUTTON, bot)
    state = await manage_regulation.start(update, context)
    assert state == AdminRegulationStates.MENU

    field_label = next(
        label for label, val in context.user_data["_choices"].items() if val == "max_duration_hours"
    )
    update = make_text_update(2, ADMIN_TELEGRAM_ID, field_label, bot)
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
    creation_now = floor_to_slot(utc_now(), 30) - timedelta(days=2)
    start = creation_now + timedelta(hours=1)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation, now=creation_now)

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, usage_report.MENU_BUTTON, bot)
    state = await usage_report.start(update, context)
    assert state == AdminUsageStates.CHOOSE_SCOPE

    update = make_text_update(2, ADMIN_TELEGRAM_ID, "👤 By User", bot)
    state = await usage_report.choose_scope(update, context)
    assert state == AdminUsageStates.CHOOSE_RANGE

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "Past week", bot)
    state = await usage_report.choose_range(update, context)
    assert state == ConversationHandler.END

    bot.send_photo.assert_awaited_once()
    assert bot.send_photo.call_args.kwargs["photo"].startswith(b"\x89PNG")


async def test_admin_override_cancel_flow(lab_setup):
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=2)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation = reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation)
        reservation_id = reservation.id

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, reservations_admin.MENU_BUTTON, bot)
    state = await reservations_admin.start(update, context)
    assert state == AdminReservationsStates.CHOOSE_RESERVATION

    reservation_label = _first_choice_label(context)
    update = make_text_update(2, ADMIN_TELEGRAM_ID, reservation_label, bot)
    state = await reservations_admin.choose_reservation(update, context)
    assert state == AdminReservationsStates.CONFIRM_CANCEL

    update = make_text_update(3, ADMIN_TELEGRAM_ID, CONFIRM, bot)
    state = await reservations_admin.confirm_cancel(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        from dml_bot.db.models.reservation import Reservation, ReservationStatus

        cancelled = session.get(Reservation, reservation_id)
    assert cancelled.status == ReservationStatus.CANCELLED


async def test_admin_rename_and_delete_user(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot)
    await manage_users.start(update, context)
    alice_label = next(label for label in context.user_data["_choices"] if label.startswith("Alice"))

    update = make_text_update(2, ADMIN_TELEGRAM_ID, alice_label, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.MENU  # detail screen (same state as the list)

    rename_label = next(
        label for label, val in context.user_data["_choices"].items() if isinstance(val, tuple) and val[0] == "rename"
    )
    update = make_text_update(3, ADMIN_TELEGRAM_ID, rename_label, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.RENAME

    update = make_text_update(4, ADMIN_TELEGRAM_ID, "Alice Renamed", bot)
    state = await manage_users.receive_rename(update, context)
    assert state == AdminUserStates.MENU

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
    assert user.full_name == "Alice Renamed"

    renamed_label = next(label for label in context.user_data["_choices"] if label.startswith("Alice Renamed"))
    update = make_text_update(5, ADMIN_TELEGRAM_ID, renamed_label, bot)
    await manage_users.menu_choice(update, context)
    delete_label = next(
        label for label, val in context.user_data["_choices"].items() if isinstance(val, tuple) and val[0] == "delete"
    )
    update = make_text_update(6, ADMIN_TELEGRAM_ID, delete_label, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.CONFIRM_DELETE

    update = make_text_update(7, ADMIN_TELEGRAM_ID, CONFIRM, bot)
    state = await manage_users.confirm_delete(update, context)
    assert state == AdminUserStates.MENU

    with session_scope() as session:
        assert user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"]) is None


async def test_admin_server_and_gpu_rename_deactivate_delete(lab_setup):
    server_id = lab_setup["server_id"]
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_servers.MENU_BUTTON, bot)
    state = await manage_servers.start(update, context)
    assert state == AdminServerStates.MENU

    server_label = next(label for label in context.user_data["_choices"] if label.startswith("lab-server-1"))
    update = make_text_update(2, ADMIN_TELEGRAM_ID, server_label, bot)
    state = await manage_servers.menu_choice(update, context)
    assert state == AdminServerStates.SERVER_DETAIL

    rename_label = next(
        label for label, val in context.user_data["_choices"].items() if val == ("rename_server", server_id)
    )
    update = make_text_update(3, ADMIN_TELEGRAM_ID, rename_label, bot)
    state = await manage_servers.server_detail_choice(update, context)
    assert state == AdminServerStates.RENAME_SERVER

    update = make_text_update(4, ADMIN_TELEGRAM_ID, "lab-server-renamed", bot)
    state = await manage_servers.receive_rename_server(update, context)
    assert state == AdminServerStates.SERVER_DETAIL

    with session_scope() as session:
        server = session.get(Server, server_id)
        assert server.name == "lab-server-renamed"

    deactivate_label = next(
        label for label, val in context.user_data["_choices"].items() if val == ("toggle_server_active", server_id)
    )
    update = make_text_update(5, ADMIN_TELEGRAM_ID, deactivate_label, bot)
    state = await manage_servers.server_detail_choice(update, context)
    assert state == AdminServerStates.SERVER_DETAIL

    with session_scope() as session:
        server = session.get(Server, server_id)
        assert server.is_active is False

    gpu_label = next(
        label for label, val in context.user_data["_choices"].items() if isinstance(val, tuple) and val[0] == "gpu"
    )
    gpu_id = context.user_data["_choices"][gpu_label][1]
    update = make_text_update(6, ADMIN_TELEGRAM_ID, gpu_label, bot)
    state = await manage_servers.server_detail_choice(update, context)
    assert state == AdminServerStates.GPU_DETAIL

    rename_gpu_label = next(
        label for label, val in context.user_data["_choices"].items() if val == ("rename_gpu", gpu_id)
    )
    update = make_text_update(7, ADMIN_TELEGRAM_ID, rename_gpu_label, bot)
    state = await manage_servers.gpu_detail_choice(update, context)
    assert state == AdminServerStates.RENAME_GPU

    update = make_text_update(8, ADMIN_TELEGRAM_ID, "NVIDIA H100", bot)
    state = await manage_servers.receive_rename_gpu(update, context)
    assert state == AdminServerStates.GPU_DETAIL

    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        assert gpu.model_name == "NVIDIA H100"

    # Back from the GPU detail screen should return to the server detail screen, not exit.
    update = make_text_update(9, ADMIN_TELEGRAM_ID, BACK, bot)
    state = await manage_servers.gpu_detail_choice(update, context)
    assert state == AdminServerStates.SERVER_DETAIL

    delete_server_label = next(
        label for label, val in context.user_data["_choices"].items() if val == ("delete_server", server_id)
    )
    update = make_text_update(10, ADMIN_TELEGRAM_ID, delete_server_label, bot)
    state = await manage_servers.server_detail_choice(update, context)
    assert state == AdminServerStates.CONFIRM_DELETE_SERVER

    update = make_text_update(11, ADMIN_TELEGRAM_ID, CONFIRM, bot)
    state = await manage_servers.confirm_delete_server(update, context)
    assert state == AdminServerStates.MENU

    with session_scope() as session:
        assert session.get(Server, server_id) is None
        assert session.get(GPU, gpu_id) is None


async def test_admin_back_and_main_menu_navigation(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot)
    await manage_users.start(update, context)
    alice_label = next(label for label in context.user_data["_choices"] if label.startswith("Alice"))

    update = make_text_update(2, ADMIN_TELEGRAM_ID, alice_label, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.MENU
    assert context.user_data["_viewing_user_id"] is not None

    # Back from the detail screen returns to the list, one step back -- not straight to the main menu.
    update = make_text_update(3, ADMIN_TELEGRAM_ID, BACK, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.MENU
    assert "_viewing_user_id" not in context.user_data

    # Back again from the list (the first screen) exits the wizard entirely.
    update = make_text_update(4, ADMIN_TELEGRAM_ID, BACK, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == ConversationHandler.END

    # Main Menu exits instantly from any screen, regardless of depth.
    bot2 = FakeBot()
    context2 = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    update = make_text_update(5, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot2)
    await manage_users.start(update, context2)
    alice_label2 = next(label for label in context2.user_data["_choices"] if label.startswith("Alice"))
    update = make_text_update(6, ADMIN_TELEGRAM_ID, alice_label2, bot2)
    await manage_users.menu_choice(update, context2)

    update = make_text_update(7, ADMIN_TELEGRAM_ID, MAIN_MENU, bot2)
    state = await manage_users.menu_choice(update, context2)
    assert state == ConversationHandler.END
