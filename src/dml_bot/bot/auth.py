from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import ContextTypes

from dml_bot.db.models.user import User
from dml_bot.services import user_service


def is_admin(telegram_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return telegram_id in context.bot_data["admin_ids"]


def get_active_user(session: Session, telegram_id: int) -> User | None:
    user = user_service.get_user_by_telegram_id(session, telegram_id)
    if user is None or not user.is_active:
        return None
    return user


async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not is_admin(update.effective_user.id, context):
        await update.effective_message.reply_text("⛔ Admins only.")
        return False
    return True
