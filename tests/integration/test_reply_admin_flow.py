from datetime import timedelta

from telegram.ext import ConversationHandler

from dml_bot.bot_reply.handlers import common as bot_reply_common
from dml_bot.bot_reply.handlers.admin import (
    manage_regulation,
    manage_servers,
    manage_users,
    reservations_admin,
    usage_report,
)
from dml_bot.bot_reply.keyboards import BACK, BACK_TO_MAIN, CONFIRM, DONE, MAIN_MENU
from dml_bot.bot_reply.states import (
    AdminRegulationStates,
    AdminReservationsStates,
    AdminServerStates,
    AdminUsageStates,
    AdminUserStates,
)
from dml_bot.db.models.gpu import GPU
from dml_bot.db.models.invite_code import InviteCode
from dml_bot.db.models.server import Server
from dml_bot.db.session import session_scope
from dml_bot.services import (
    invite_service,
    regulation_service,
    reservation_service,
    server_access_service,
    server_service,
    user_service,
)
from dml_bot.utils.time_utils import floor_to_slot, utc_now
from tests.integration.telegram_helpers import FakeBot, make_context, make_text_update

ADMIN_TELEGRAM_ID = 999


def _first_choice_label(context) -> str:
    return next(iter(context.user_data["_choices"]))


async def test_admin_add_user_flow_creates_invite(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot)
    state = await manage_users.start(update, context)
    assert state == AdminUserStates.MENU

    update = make_text_update(2, ADMIN_TELEGRAM_ID, manage_users.ADD_USER, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == AdminUserStates.ADD_FULL_NAME

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "Charlie", bot)
    state = await manage_users.receive_full_name(update, context)
    assert state == AdminUserStates.ADD_SERVER_ACCESS

    server_label = _first_choice_label(context)
    update = make_text_update(4, ADMIN_TELEGRAM_ID, server_label, bot)
    state = await manage_users.choose_new_user_access(update, context)
    assert state == AdminUserStates.ADD_SERVER_ACCESS  # toggled on, screen re-rendered

    update = make_text_update(5, ADMIN_TELEGRAM_ID, DONE, bot)
    state = await manage_users.choose_new_user_access(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        invites = invite_service.list_pending_invites(session)
        assert len(invites) == 1
        assert invites[0].full_name == "Charlie"
        server_ids = {int(x) for x in invites[0].server_ids.split(",") if x}
    assert server_ids == {lab_setup["server_id"]}


async def test_add_user_requires_at_least_one_server(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    await manage_users.start(make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot), context)
    await manage_users.menu_choice(make_text_update(2, ADMIN_TELEGRAM_ID, manage_users.ADD_USER, bot), context)
    state = await manage_users.receive_full_name(make_text_update(3, ADMIN_TELEGRAM_ID, "Dana", bot), context)
    assert state == AdminUserStates.ADD_SERVER_ACCESS

    # Tapping Done with nothing selected is rejected -- at least one server is required.
    state = await manage_users.choose_new_user_access(make_text_update(4, ADMIN_TELEGRAM_ID, DONE, bot), context)
    assert state == AdminUserStates.ADD_SERVER_ACCESS

    with session_scope() as session:
        assert invite_service.list_pending_invites(session) == []


async def test_student_redeems_invite_and_gets_server_access(lab_setup):
    with session_scope() as session:
        invite = invite_service.create_invite(session, full_name="Charlie", server_ids={lab_setup["server_id"]})
        code = invite.code

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID}, args=[code])
    update = make_text_update(1, 424242, f"/start {code}", bot)

    await bot_reply_common.start_command(update, context)

    with session_scope() as session:
        new_user = user_service.get_user_by_telegram_id(session, 424242)
        assert new_user is not None
        assert new_user.full_name == "Charlie"
        assert server_access_service.list_accessible_server_ids(session, new_user.id) == {lab_setup["server_id"]}
        assert invite_service.list_pending_invites(session) == []


async def test_admin_revokes_pending_invite(lab_setup):
    with session_scope() as session:
        invite = invite_service.create_invite(session, full_name="Charlie")
        invite_id = invite.id

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    await manage_users.start(make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot), context)

    invite_label = next(l for l in context.user_data["_choices"] if "📨" in l)
    state = await manage_users.menu_choice(make_text_update(2, ADMIN_TELEGRAM_ID, invite_label, bot), context)
    assert state == AdminUserStates.MENU

    with session_scope() as session:
        assert invite_service.list_pending_invites(session) == []
        assert session.get(InviteCode, invite_id) is None


async def test_admin_grants_and_revokes_server_access(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    server_id = lab_setup["server_id"]
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        user_id = user.id
        assert server_access_service.list_accessible_server_ids(session, user_id) == {server_id}

    await manage_users.start(make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot), context)
    user_label = _first_choice_label(context)
    state = await manage_users.menu_choice(make_text_update(2, ADMIN_TELEGRAM_ID, user_label, bot), context)
    assert state == AdminUserStates.MENU  # detail screen (same enum value, dual-purpose state)

    # find the "Server Access" action specifically, since the detail screen has several actions
    access_label = next(l for l in context.user_data["_choices"] if "Server Access" in l)
    state = await manage_users.menu_choice(make_text_update(3, ADMIN_TELEGRAM_ID, access_label, bot), context)
    assert state == AdminUserStates.EDIT_SERVER_ACCESS

    server_label = _first_choice_label(context)
    assert server_label.startswith("✅")  # pre-checked since Alice already has access
    state = await manage_users.choose_edit_access(make_text_update(4, ADMIN_TELEGRAM_ID, server_label, bot), context)
    assert state == AdminUserStates.EDIT_SERVER_ACCESS

    state = await manage_users.choose_edit_access(make_text_update(5, ADMIN_TELEGRAM_ID, DONE, bot), context)
    assert state == AdminUserStates.MENU

    with session_scope() as session:
        assert server_access_service.list_accessible_server_ids(session, user_id) == set()  # revoked


async def test_user_and_server_lists_render_as_a_2_column_grid(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    with session_scope() as session:
        for i in range(3):
            user_service.register_user(session, telegram_id=100 + i, full_name=f"Student{i}")
            server_service.create_server(session, f"extra-server-{i}")

    await manage_users.start(make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot), context)
    users_markup = bot.send_message.call_args.kwargs["reply_markup"]
    users_item_rows = [row for row in users_markup.keyboard if len(row) == 2]
    assert len(users_item_rows) >= 1

    await manage_servers.start(make_text_update(2, ADMIN_TELEGRAM_ID, manage_servers.MENU_BUTTON, bot), context)
    servers_markup = bot.send_message.call_args.kwargs["reply_markup"]
    servers_item_rows = [row for row in servers_markup.keyboard if len(row) == 2]
    assert len(servers_item_rows) >= 1


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


async def test_bootstrap_admin_can_grant_and_revoke_admin_role(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot)
    await manage_users.start(update, context)
    alice_label = next(label for label in context.user_data["_choices"] if label.startswith("Alice"))

    update = make_text_update(2, ADMIN_TELEGRAM_ID, alice_label, bot)
    await manage_users.menu_choice(update, context)

    grant_label = next(
        label for label, val in context.user_data["_choices"].items()
        if isinstance(val, tuple) and val[0] == "toggle_admin"
    )
    assert grant_label.startswith("🛡 Grant admin")
    update = make_text_update(3, ADMIN_TELEGRAM_ID, grant_label, bot)
    await manage_users.menu_choice(update, context)

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        assert user.is_admin is True

    revoke_label = next(
        label for label, val in context.user_data["_choices"].items()
        if isinstance(val, tuple) and val[0] == "toggle_admin"
    )
    assert revoke_label.startswith("🛡 Revoke admin")
    update = make_text_update(4, ADMIN_TELEGRAM_ID, revoke_label, bot)
    await manage_users.menu_choice(update, context)

    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, lab_setup["telegram_id"])
        assert user.is_admin is False


async def test_promoted_admin_cannot_grant_admin_role_and_gets_no_toggle_button(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    with session_scope() as session:
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        user_service.set_admin(session, user, True)

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    # The promoted (non-bootstrap) admin opens Manage Users and views their own record.
    update = make_text_update(1, telegram_id, manage_users.MENU_BUTTON, bot)
    await manage_users.start(update, context)
    alice_label = next(label for label in context.user_data["_choices"] if label.startswith("Alice"))

    update = make_text_update(2, telegram_id, alice_label, bot)
    await manage_users.menu_choice(update, context)

    assert not any(
        isinstance(val, tuple) and val[0] == "toggle_admin"
        for val in context.user_data["_choices"].values()
    )


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


async def test_admin_can_set_cancellation_notice_cutoff_including_zero(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_regulation.MENU_BUTTON, bot)
    await manage_regulation.start(update, context)

    field_label = next(
        label
        for label, val in context.user_data["_choices"].items()
        if val == "min_cancellation_notice_minutes"
    )
    update = make_text_update(2, ADMIN_TELEGRAM_ID, field_label, bot)
    state = await manage_regulation.choose_field(update, context)
    assert state == AdminRegulationStates.EDIT_VALUE

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "120", bot)
    state = await manage_regulation.receive_value(update, context)
    assert state == ConversationHandler.END
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    assert regulation.min_cancellation_notice_minutes == 120

    # 0 is a valid value for this field specifically (disables the cutoff) -- unlike every other
    # regulation field, which requires a strictly positive number.
    update = make_text_update(4, ADMIN_TELEGRAM_ID, manage_regulation.MENU_BUTTON, bot)
    await manage_regulation.start(update, context)
    field_label = next(
        label
        for label, val in context.user_data["_choices"].items()
        if val == "min_cancellation_notice_minutes"
    )
    update = make_text_update(5, ADMIN_TELEGRAM_ID, field_label, bot)
    await manage_regulation.choose_field(update, context)
    update = make_text_update(6, ADMIN_TELEGRAM_ID, "0", bot)
    state = await manage_regulation.receive_value(update, context)
    assert state == ConversationHandler.END
    with session_scope() as session:
        regulation = regulation_service.get_regulation(session)
    assert regulation.min_cancellation_notice_minutes == 0


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


async def test_admin_usage_report_by_gpu_labels_include_ram(lab_setup, monkeypatch):
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    creation_now = floor_to_slot(utc_now(), 30) - timedelta(days=2)
    start = creation_now + timedelta(hours=1)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation, now=creation_now)

    captured = {}

    def _fake_render_bar_chart(labels, values, title, ylabel):
        captured["labels"] = labels
        return b"\x89PNG"

    monkeypatch.setattr(usage_report, "render_bar_chart", _fake_render_bar_chart)

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, usage_report.MENU_BUTTON, bot)
    await usage_report.start(update, context)

    update = make_text_update(2, ADMIN_TELEGRAM_ID, "🖥 By GPU", bot)
    await usage_report.choose_scope(update, context)

    update = make_text_update(3, ADMIN_TELEGRAM_ID, "Past week", bot)
    await usage_report.choose_range(update, context)

    assert captured["labels"], "expected at least one GPU label"
    assert all("GB" in label or "MB" in label for label in captured["labels"])


async def test_admin_historical_availability_shows_a_reservation_from_long_ago(lab_setup):
    """Reservations are kept forever (scheduling.jobs.run_cleanup no longer deletes them), so an
    admin must be able to pull up the availability chart for a window from months back."""
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    far_past = utc_now() - timedelta(days=200)
    start = floor_to_slot(far_past, 30) + timedelta(hours=1)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation, now=far_past)

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, usage_report.MENU_BUTTON, bot)
    state = await usage_report.start(update, context)
    assert state == AdminUsageStates.CHOOSE_SCOPE

    update = make_text_update(2, ADMIN_TELEGRAM_ID, "📅 Historical Availability", bot)
    state = await usage_report.choose_scope(update, context)
    assert state == AdminUsageStates.CHOOSE_HISTORICAL_GPU

    gpu_label = _first_choice_label(context)
    update = make_text_update(3, ADMIN_TELEGRAM_ID, gpu_label, bot)
    state = await usage_report.choose_historical_gpu(update, context)
    assert state == AdminUsageStates.TYPE_HISTORICAL_START_DATE

    start_date_text = (far_past.date() - timedelta(days=1)).isoformat()
    update = make_text_update(4, ADMIN_TELEGRAM_ID, start_date_text, bot)
    state = await usage_report.receive_historical_start_date(update, context)
    assert state == AdminUsageStates.TYPE_HISTORICAL_DURATION_DAYS

    update = make_text_update(5, ADMIN_TELEGRAM_ID, "5", bot)
    state = await usage_report.receive_historical_duration(update, context)
    assert state == ConversationHandler.END

    texts = [c.kwargs["text"] for c in bot.send_message.call_args_list]
    assert any("historical availability" in t for t in texts)
    assert any("<pre>" in t for t in texts)  # default renderer (unseeded) is the legacy text chart


async def test_admin_historical_availability_rejects_bad_date_and_duration(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    await usage_report.start(make_text_update(1, ADMIN_TELEGRAM_ID, usage_report.MENU_BUTTON, bot), context)
    await usage_report.choose_scope(
        make_text_update(2, ADMIN_TELEGRAM_ID, "📅 Historical Availability", bot), context
    )
    gpu_label = _first_choice_label(context)
    await usage_report.choose_historical_gpu(make_text_update(3, ADMIN_TELEGRAM_ID, gpu_label, bot), context)

    state = await usage_report.receive_historical_start_date(
        make_text_update(4, ADMIN_TELEGRAM_ID, "not-a-date", bot), context
    )
    assert state == AdminUsageStates.TYPE_HISTORICAL_START_DATE

    update = make_text_update(5, ADMIN_TELEGRAM_ID, "2026-01-01", bot)
    state = await usage_report.receive_historical_start_date(update, context)
    assert state == AdminUsageStates.TYPE_HISTORICAL_DURATION_DAYS

    for bad in ("0", "-3", "lots"):
        state = await usage_report.receive_historical_duration(
            make_text_update(6, ADMIN_TELEGRAM_ID, bad, bot), context
        )
        assert state == AdminUsageStates.TYPE_HISTORICAL_DURATION_DAYS


async def test_admin_historical_availability_back_and_main_menu(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    await usage_report.start(make_text_update(1, ADMIN_TELEGRAM_ID, usage_report.MENU_BUTTON, bot), context)
    await usage_report.choose_scope(
        make_text_update(2, ADMIN_TELEGRAM_ID, "📅 Historical Availability", bot), context
    )

    # Back on the GPU step returns to the scope screen (first screen of the sub-flow).
    state = await usage_report.choose_historical_gpu(make_text_update(3, ADMIN_TELEGRAM_ID, BACK, bot), context)
    assert state == AdminUsageStates.CHOOSE_SCOPE

    await usage_report.choose_scope(
        make_text_update(4, ADMIN_TELEGRAM_ID, "📅 Historical Availability", bot), context
    )
    gpu_label = _first_choice_label(context)
    await usage_report.choose_historical_gpu(make_text_update(5, ADMIN_TELEGRAM_ID, gpu_label, bot), context)

    # Main Menu exits instantly from the middle of the sub-flow.
    state = await usage_report.receive_historical_start_date(
        make_text_update(6, ADMIN_TELEGRAM_ID, MAIN_MENU, bot), context
    )
    assert state == ConversationHandler.END


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
    assert state == AdminReservationsStates.CHOOSE_SCOPE

    update = make_text_update(2, ADMIN_TELEGRAM_ID, reservations_admin.SCOPE_ALL, bot)
    state = await reservations_admin.choose_scope(update, context)
    assert state == AdminReservationsStates.CHOOSE_RESERVATION

    reservation_label = _first_choice_label(context)
    assert "→" in reservation_label  # start and end both present
    assert "GB" in reservation_label or "MB" in reservation_label  # RAM present
    update = make_text_update(3, ADMIN_TELEGRAM_ID, reservation_label, bot)
    state = await reservations_admin.choose_reservation(update, context)
    assert state == AdminReservationsStates.CONFIRM_CANCEL

    update = make_text_update(4, ADMIN_TELEGRAM_ID, CONFIRM, bot)
    state = await reservations_admin.confirm_cancel(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        from dml_bot.db.models.reservation import Reservation, ReservationStatus

        cancelled = session.get(Reservation, reservation_id)
    assert cancelled.status == ReservationStatus.CANCELLED

    notify_calls = [c for c in bot.send_message.call_args_list if c.kwargs.get("chat_id") == telegram_id]
    assert len(notify_calls) == 1
    assert "cancelled by an admin" in notify_calls[0].kwargs["text"]


async def test_admin_cancel_bypasses_student_notice_cutoff(lab_setup):
    """Admin cancellations must always be allowed, even when the reservation falls inside the
    student self-cancellation notice cutoff -- the cutoff only restricts student-initiated
    cancellations, not admin overrides."""
    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    start = floor_to_slot(utc_now(), 30) + timedelta(hours=2)
    end = start + timedelta(hours=2)
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        reservation = reservation_service.create_reservation(session, user, gpu, start, end, 4096, regulation)
        reservation_id = reservation.id
        regulation_service.update_regulation(session, updated_by=1, min_cancellation_notice_minutes=10**8)

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, reservations_admin.MENU_BUTTON, bot)
    await reservations_admin.start(update, context)
    update = make_text_update(2, ADMIN_TELEGRAM_ID, reservations_admin.SCOPE_ALL, bot)
    await reservations_admin.choose_scope(update, context)

    reservation_label = _first_choice_label(context)
    update = make_text_update(3, ADMIN_TELEGRAM_ID, reservation_label, bot)
    await reservations_admin.choose_reservation(update, context)

    update = make_text_update(4, ADMIN_TELEGRAM_ID, CONFIRM, bot)
    state = await reservations_admin.confirm_cancel(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        from dml_bot.db.models.reservation import Reservation, ReservationStatus

        cancelled = session.get(Reservation, reservation_id)
    assert cancelled.status == ReservationStatus.CANCELLED


async def test_admin_reservations_by_user_scope_bulk_cancels_for_that_user(lab_setup):
    from dml_bot.db.models.reservation import Reservation, ReservationStatus

    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        user_id = user.id
        start1 = floor_to_slot(utc_now(), 30) + timedelta(hours=2)
        r1 = reservation_service.create_reservation(session, user, gpu, start1, start1 + timedelta(hours=1), 4096, regulation)
        start2 = start1 + timedelta(hours=3)
        r2 = reservation_service.create_reservation(session, user, gpu, start2, start2 + timedelta(hours=1), 4096, regulation)
        r1_id, r2_id = r1.id, r2.id

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, reservations_admin.MENU_BUTTON, bot)
    await reservations_admin.start(update, context)

    update = make_text_update(2, ADMIN_TELEGRAM_ID, reservations_admin.SCOPE_BY_USER, bot)
    state = await reservations_admin.choose_scope(update, context)
    assert state == AdminReservationsStates.CHOOSE_USER

    user_label = next(label for label in context.user_data["_choices"] if label.startswith("Alice"))
    update = make_text_update(3, ADMIN_TELEGRAM_ID, user_label, bot)
    state = await reservations_admin.choose_user(update, context)
    assert state == AdminReservationsStates.CHOOSE_RESERVATION

    list_markup = bot.send_message.call_args.kwargs["reply_markup"]
    button_texts = [btn.text for row in list_markup.keyboard for btn in row]
    assert reservations_admin.CANCEL_ALL_USER in button_texts
    assert reservations_admin.CANCEL_ALL_LAB not in button_texts

    update = make_text_update(4, ADMIN_TELEGRAM_ID, reservations_admin.CANCEL_ALL_USER, bot)
    state = await reservations_admin.choose_reservation(update, context)
    assert state == AdminReservationsStates.CONFIRM_CANCEL_ALL_USER

    update = make_text_update(5, ADMIN_TELEGRAM_ID, CONFIRM, bot)
    state = await reservations_admin.confirm_cancel_all_user(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        assert session.get(Reservation, r1_id).status == ReservationStatus.CANCELLED
        assert session.get(Reservation, r2_id).status == ReservationStatus.CANCELLED
        assert reservation_service.list_active_reservations_for_user(session, user_id) == []

    notify_calls = [c for c in bot.send_message.call_args_list if c.kwargs.get("chat_id") == telegram_id]
    assert len(notify_calls) == 2  # one notification per cancelled reservation
    assert all("cancelled by an admin" in c.kwargs["text"] for c in notify_calls)


async def test_admin_reservations_cancel_all_lab_wide_requires_typed_phrase(lab_setup):
    from dml_bot.db.models.reservation import Reservation, ReservationStatus

    gpu_id, telegram_id = lab_setup["gpu_id"], lab_setup["telegram_id"]
    with session_scope() as session:
        gpu = session.get(GPU, gpu_id)
        regulation = regulation_service.get_regulation(session)
        user = user_service.get_user_by_telegram_id(session, telegram_id)
        start1 = floor_to_slot(utc_now(), 30) + timedelta(hours=2)
        r1 = reservation_service.create_reservation(session, user, gpu, start1, start1 + timedelta(hours=1), 4096, regulation)
        start2 = start1 + timedelta(hours=3)
        r2 = reservation_service.create_reservation(session, user, gpu, start2, start2 + timedelta(hours=1), 4096, regulation)
        r1_id, r2_id = r1.id, r2.id

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, reservations_admin.MENU_BUTTON, bot)
    await reservations_admin.start(update, context)

    update = make_text_update(2, ADMIN_TELEGRAM_ID, reservations_admin.SCOPE_ALL, bot)
    state = await reservations_admin.choose_scope(update, context)
    assert state == AdminReservationsStates.CHOOSE_RESERVATION

    list_markup = bot.send_message.call_args.kwargs["reply_markup"]
    button_texts = [btn.text for row in list_markup.keyboard for btn in row]
    assert reservations_admin.CANCEL_ALL_LAB in button_texts

    update = make_text_update(3, ADMIN_TELEGRAM_ID, reservations_admin.CANCEL_ALL_LAB, bot)
    state = await reservations_admin.choose_reservation(update, context)
    assert state == AdminReservationsStates.TYPE_CONFIRM_CANCEL_ALL_LAB

    # Wrong text does not cancel anything and re-prompts for the exact phrase.
    update = make_text_update(4, ADMIN_TELEGRAM_ID, "yes please", bot)
    state = await reservations_admin.confirm_cancel_all_lab(update, context)
    assert state == AdminReservationsStates.TYPE_CONFIRM_CANCEL_ALL_LAB
    with session_scope() as session:
        assert session.get(Reservation, r1_id).status == ReservationStatus.ACTIVE

    # The exact phrase (case-insensitive) cancels every upcoming reservation lab-wide.
    update = make_text_update(5, ADMIN_TELEGRAM_ID, "cancel all", bot)
    state = await reservations_admin.confirm_cancel_all_lab(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        assert session.get(Reservation, r1_id).status == ReservationStatus.CANCELLED
        assert session.get(Reservation, r2_id).status == ReservationStatus.CANCELLED

    notify_calls = [c for c in bot.send_message.call_args_list if c.kwargs.get("chat_id") == telegram_id]
    assert len(notify_calls) == 2  # one notification per cancelled reservation
    assert all("cancelled by an admin" in c.kwargs["text"] for c in notify_calls)


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
    server_id, gpu_id = lab_setup["server_id"], lab_setup["gpu_id"]
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_servers.MENU_BUTTON, bot)
    state = await manage_servers.start(update, context)
    assert state == AdminServerStates.MENU

    server_label = next(label for label in context.user_data["_choices"] if label.startswith("lab-server-1"))
    update = make_text_update(2, ADMIN_TELEGRAM_ID, server_label, bot)
    state = await manage_servers.menu_choice(update, context)
    assert state == AdminServerStates.SERVER_DETAIL

    gpu_button_label = next(
        label for label, val in context.user_data["_choices"].items() if val == ("gpu", gpu_id)
    )
    assert "GB" in gpu_button_label or "MB" in gpu_button_label

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

    # Back again from the list (the first screen) steps up to the Admin Panel menu, not the Main Menu.
    update = make_text_update(4, ADMIN_TELEGRAM_ID, BACK, bot)
    state = await manage_users.menu_choice(update, context)
    assert state == ConversationHandler.END
    assert bot.send_message.call_args.kwargs["text"] == "Admin panel:"
    admin_panel_texts = [btn.text for row in bot.send_message.call_args.kwargs["reply_markup"].keyboard for btn in row]
    assert BACK_TO_MAIN in admin_panel_texts
    assert MAIN_MENU not in admin_panel_texts

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


async def test_bootstrap_admin_is_marked_with_key_emoji_in_user_list_and_detail(lab_setup):
    with session_scope() as session:
        user_service.register_user(session, telegram_id=ADMIN_TELEGRAM_ID, full_name="Dr. Admin")

    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})
    update = make_text_update(1, ADMIN_TELEGRAM_ID, manage_users.MENU_BUTTON, bot)
    await manage_users.start(update, context)

    admin_label = next(label for label in context.user_data["_choices"] if label.startswith("Dr. Admin"))
    alice_label = next(label for label in context.user_data["_choices"] if label.startswith("Alice"))
    assert "🔑" in admin_label
    assert "🔑" not in alice_label

    update = make_text_update(2, ADMIN_TELEGRAM_ID, admin_label, bot)
    await manage_users.menu_choice(update, context)
    detail_text = bot.send_message.call_args.kwargs["text"]
    assert "🔑 yes" in detail_text
