from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from dml_bot.bot.auth import require_admin
from dml_bot.bot_reply.choice_map import resolve_choice
from dml_bot.bot_reply.handlers.common import cancel_wizard, cancel_wizard_to_admin, show_main_menu
from dml_bot.bot_reply.keyboards import BACK, MAIN_MENU, action_keyboard
from dml_bot.bot_reply.states import AdminChartStates
from dml_bot.db.session import session_scope
from dml_bot.services import chart_settings_service

MENU_BUTTON = "🎨 Chart Style"


async def _render_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with session_scope() as session:
        current = chart_settings_service.get_renderer(session)
    actions = [
        (f"{'✅ ' if renderer == current else ''}{chart_settings_service.RENDERER_LABELS[renderer]}", renderer)
        for renderer in chart_settings_service.RENDERERS
    ]
    markup = action_keyboard(context, actions)
    await update.effective_message.reply_text(
        "Chart renderer for Reserve GPU / Schedule / Watches' RAM chart (tap to switch):",
        reply_markup=markup,
    )
    return AdminChartStates.MENU


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_admin(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    return await _render_menu(update, context)


async def choose_renderer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text
    if text == MAIN_MENU:
        return await cancel_wizard(update, context)
    if text == BACK:
        return await cancel_wizard_to_admin(update, context)

    renderer = resolve_choice(context, text)
    if renderer is None:
        await update.effective_message.reply_text("Please use one of the buttons below.")
        return await _render_menu(update, context)

    with session_scope() as session:
        chart_settings_service.set_renderer(session, update.effective_user.id, renderer)

    context.user_data.clear()
    await update.effective_message.reply_text(
        f"✅ Chart renderer set to {chart_settings_service.RENDERER_LABELS[renderer]}."
    )
    await show_main_menu(update, context)
    return ConversationHandler.END


def chart_settings_conversation() -> ConversationHandler:
    text_filter = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Text([MENU_BUTTON]), start)],
        states={
            AdminChartStates.MENU: [MessageHandler(text_filter, choose_renderer)],
        },
        fallbacks=[MessageHandler(text_filter, cancel_wizard), CommandHandler("cancel", cancel_wizard)],
        name="reply_admin_chart_settings_conversation",
        persistent=False,
    )
