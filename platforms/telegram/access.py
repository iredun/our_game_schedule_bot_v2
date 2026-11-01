import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from platforms.telegram.messaging import send_notice


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
    return True
