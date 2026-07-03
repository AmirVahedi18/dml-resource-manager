"""Resolves a reply-keyboard button press back to the value it represents.

Reply keyboards can't carry a hidden id the way inline callback_data does -- a button press just
sends back its visible label as an ordinary text message. Every list-selection screen stores the
{label: value} mapping it just rendered; the next handler looks the incoming text up in it.
"""
from telegram.ext import ContextTypes

_KEY = "_choices"


def store_choices(context: ContextTypes.DEFAULT_TYPE, mapping: dict) -> None:
    context.user_data[_KEY] = mapping


def resolve_choice(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Returns the value stored for `text`, or None if `text` isn't one of the current choices."""
    return context.user_data.get(_KEY, {}).get(text)
