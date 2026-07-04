"""Lightweight stand-ins for driving bot handler coroutines without a live Telegram connection.

Real telegram.Update/Message/CallbackQuery objects are used (so handler code that calls
update.callback_query.edit_message_text(...) etc. behaves exactly as in production); only the
network-facing Bot methods are replaced with recording async mocks.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram import CallbackQuery, Chat, Message, Update, User

from dml_bot.config.schema import AppConfig


class FakeBot:
    def __init__(self):
        self.edit_message_text = AsyncMock(return_value=None)
        self.send_message = AsyncMock(return_value=None)
        self.send_photo = AsyncMock(return_value=None)
        self.answer_callback_query = AsyncMock(return_value=True)


def make_callback_update(update_id: int, telegram_id: int, data: str, bot: FakeBot) -> Update:
    user = User(id=telegram_id, first_name="Test", is_bot=False)
    chat = Chat(id=telegram_id, type="private")
    message = Message(message_id=update_id, date=datetime.now(timezone.utc), chat=chat, from_user=user)
    message.set_bot(bot)
    callback_query = CallbackQuery(
        id=str(update_id), from_user=user, chat_instance="instance", data=data, message=message
    )
    callback_query.set_bot(bot)
    update = Update(update_id=update_id, callback_query=callback_query)
    update.set_bot(bot)
    return update


def make_text_update(update_id: int, telegram_id: int, text: str, bot: FakeBot) -> Update:
    user = User(id=telegram_id, first_name="Test", is_bot=False)
    chat = Chat(id=telegram_id, type="private")
    message = Message(message_id=update_id, date=datetime.now(timezone.utc), chat=chat, from_user=user, text=text)
    message.set_bot(bot)
    update = Update(update_id=update_id, message=message)
    update.set_bot(bot)
    return update


def make_context(
    admin_ids: set[int] | None = None, config: AppConfig | None = None, args: list[str] | None = None
) -> SimpleNamespace:
    bot_data = {"admin_ids": admin_ids or set(), "config": config or AppConfig()}
    return SimpleNamespace(
        user_data={}, application=SimpleNamespace(bot_data=bot_data), bot_data=bot_data, args=args or []
    )
