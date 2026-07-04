from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import ContextTypes

from dml_bot.db.models.user import User
from dml_bot.db.session import session_scope
from dml_bot.services import user_service


def is_bootstrap_admin(telegram_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True for the fixed set of admins configured via `ADMIN_IDS` in `.env`. These can't be
    demoted through the bot -- there's always at least one way in -- and only a bootstrap admin
    may grant or revoke the DB-stored admin role (see `user_service.set_admin`)."""
    return telegram_id in context.bot_data["admin_ids"]


def is_admin(session: Session, telegram_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True for a bootstrap admin, or an active registered user promoted via the DB-stored
    `User.is_admin` role (e.g. a TA promoted by a bootstrap admin without redeploying)."""
    if is_bootstrap_admin(telegram_id, context):
        return True
    user = user_service.get_user_by_telegram_id(session, telegram_id)
    return user is not None and user.is_active and user.is_admin


def get_active_user(session: Session, telegram_id: int) -> User | None:
    user = user_service.get_user_by_telegram_id(session, telegram_id)
    if user is None or not user.is_active:
        return None
    return user


async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    with session_scope() as session:
        allowed = is_admin(session, update.effective_user.id, context)
    if not allowed:
        await update.effective_message.reply_text("⛔ Admins only.")
        return False
    return True
