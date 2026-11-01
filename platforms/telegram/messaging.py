import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes


async def delete_invoking_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message
    if message is None or not message.entities:
        return
    if not any(
        entity.type == "bot_command" and entity.offset == 0
        for entity in message.entities
    ):
        return

    try:
        await context.bot.delete_message(
            chat_id=message.chat_id,
            message_id=message.message_id,
        )
    except TelegramError:
        logging.exception(
            "Failed to delete Telegram command message %s in chat %s",
            message.message_id,
            message.chat_id,
        )


async def send_notice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    **kwargs,
):
    """Send a notice only to its requester in group chats."""
    chat = update.effective_chat
    chat_id = kwargs.pop("chat_id", chat.id)
    if chat is not None and chat.type != "private" and update.effective_user is not None:
        api_kwargs = dict(kwargs.pop("api_kwargs", {}) or {})
        api_kwargs["ephemeral_message_parameters"] = {
            "receiver_user_id": update.effective_user.id,
        }
        kwargs["api_kwargs"] = api_kwargs

    sent_message = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        **kwargs,
    )
    await delete_invoking_command(update, context)
    return sent_message
