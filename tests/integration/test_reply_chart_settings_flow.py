from telegram.ext import ConversationHandler

from dml_bot.bot_reply.handlers.admin import chart_settings_admin
from dml_bot.bot_reply.handlers.student import reserve as reserve_handlers
from dml_bot.bot_reply.handlers.student import view_schedule as schedule_handlers
from dml_bot.bot_reply.handlers.student import watch as watch_handlers
from dml_bot.bot_reply.keyboards import BACK, MAIN_MENU
from dml_bot.bot_reply.states import AdminChartStates
from dml_bot.db.session import session_scope
from dml_bot.services import chart_settings_service
from tests.integration.telegram_helpers import FakeBot, make_context, make_text_update

ADMIN_TELEGRAM_ID = 999


def _first_choice_label(context) -> str:
    return next(iter(context.user_data["_choices"]))


async def test_admin_switches_chart_renderer(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    update = make_text_update(1, ADMIN_TELEGRAM_ID, chart_settings_admin.MENU_BUTTON, bot)
    state = await chart_settings_admin.start(update, context)
    assert state == AdminChartStates.MENU

    label = next(
        label for label, value in context.user_data["_choices"].items() if value == "plotly_gantt"
    )
    update = make_text_update(2, ADMIN_TELEGRAM_ID, label, bot)
    state = await chart_settings_admin.choose_renderer(update, context)
    assert state == ConversationHandler.END

    with session_scope() as session:
        assert chart_settings_service.get_renderer(session) == "plotly_gantt"


async def test_non_admin_is_rejected(lab_setup):
    telegram_id = lab_setup["telegram_id"]
    bot = FakeBot()
    context = make_context()

    update = make_text_update(1, telegram_id, chart_settings_admin.MENU_BUTTON, bot)
    state = await chart_settings_admin.start(update, context)
    assert state == ConversationHandler.END
    assert bot.send_message.call_args.kwargs["text"] == "⛔ Admins only."


async def test_back_on_first_screen_steps_up_to_admin_panel(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    await chart_settings_admin.start(
        make_text_update(1, ADMIN_TELEGRAM_ID, chart_settings_admin.MENU_BUTTON, bot), context
    )
    update = make_text_update(2, ADMIN_TELEGRAM_ID, BACK, bot)
    state = await chart_settings_admin.choose_renderer(update, context)
    assert state == ConversationHandler.END
    assert bot.send_message.call_args.kwargs["text"] == "Admin panel:"


async def test_main_menu_exits_immediately(lab_setup):
    bot = FakeBot()
    context = make_context(admin_ids={ADMIN_TELEGRAM_ID})

    await chart_settings_admin.start(
        make_text_update(1, ADMIN_TELEGRAM_ID, chart_settings_admin.MENU_BUTTON, bot), context
    )
    update = make_text_update(2, ADMIN_TELEGRAM_ID, MAIN_MENU, bot)
    state = await chart_settings_admin.choose_renderer(update, context)
    assert state == ConversationHandler.END
    assert bot.send_message.call_args.kwargs["text"] == "Cancelled."


async def test_reserve_watch_and_schedule_all_use_the_same_plotly_setting(lab_setup):
    """Reserve GPU's and Watches' pre-date-picker availability charts, and View Schedule, all
    share the one admin-configured chart-style setting -- there's exactly one renderer choice,
    not one per screen."""
    telegram_id = lab_setup["telegram_id"]
    with session_scope() as session:
        chart_settings_service.set_renderer(session, ADMIN_TELEGRAM_ID, "plotly_bars")

    bot = FakeBot()
    context = make_context()
    await reserve_handlers.start(make_text_update(1, telegram_id, reserve_handlers.MENU_BUTTON, bot), context)
    gpu_label = next(iter(context.user_data["_choices"]))
    await reserve_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot), context)
    assert bot.send_photo.call_count == 1

    bot2 = FakeBot()
    context2 = make_context()
    await watch_handlers.start(make_text_update(1, telegram_id, watch_handlers.MENU_BUTTON, bot2), context2)
    await watch_handlers.menu_choice(make_text_update(2, telegram_id, watch_handlers.NEW_WATCH, bot2), context2)
    gpu_label2 = next(iter(context2.user_data["_choices"]))
    await watch_handlers.choose_gpu(make_text_update(3, telegram_id, gpu_label2, bot2), context2)
    assert bot2.send_photo.call_count == 1

    bot3 = FakeBot()
    context3 = make_context()
    await schedule_handlers.start(make_text_update(1, telegram_id, schedule_handlers.MENU_BUTTON, bot3), context3)
    gpu_label = next(iter(context3.user_data["_choices"]))
    await schedule_handlers.choose_gpu(make_text_update(2, telegram_id, gpu_label, bot3), context3)
    await schedule_handlers.choose_range(make_text_update(3, telegram_id, "3 days", bot3), context3)
    assert bot3.send_photo.call_count == 1
