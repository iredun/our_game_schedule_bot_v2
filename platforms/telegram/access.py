import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from platforms.telegram.messaging import send_notice
from db.models import Platform
from db.session import SessionLocal
from services.chat_member_service import ChatMemberService
from services.platform_service import PlatformService


settings = get_settings()


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.id not in settings.telegram_allowed_chat_ids:
        logging.warning(f"Unauthorized access attempt from chat ID: {update.effective_chat.id}")
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Доступ запрещен!",
        )
        return False
    if update.effective_chat.type != "private" and update.effective_user:
        with SessionLocal() as session:
            platform_service = PlatformService(session)
            account = platform_service.register_account(
                platform=Platform.TELEGRAM,
                platform_user_id=str(update.effective_user.id),
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name,
                display_name=update.effective_user.full_name,
            )
            chat = platform_service.register_chat(
                platform=Platform.TELEGRAM,
                platform_chat_id=str(update.effective_chat.id),
                title=update.effective_chat.title,
            )
            session.flush()
            ChatMemberService(session).observe_membership(
                chat_id=chat.id, user_id=account.user_id
            )
    return True
