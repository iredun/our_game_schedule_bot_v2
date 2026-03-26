import logging

from vkbottle.bot import Message

from core.config import get_settings


settings = get_settings()


async def check_access(message: Message) -> bool:
    if message.peer_id not in settings.vk_allowed_chat_ids:
        logging.warning("Unauthorized VK access attempt from chat ID: %s", message.peer_id)
        await message.answer("Доступ запрещен!")
        return False
    return True

