"""Best-effort fan-out of a shared game to every chat in its community."""

import logging

from telegram import Bot
from telegram.constants import ParseMode
from vkbottle import API

from core.config import get_settings
from db.models import GameStatus, Platform
from db.session import SessionLocal
from platforms.telegram.consts import REPLY_MARKUP as TELEGRAM_MARKUP
from platforms.telegram.formatting import generate_message as telegram_text
from platforms.vk.consts import REPLY_MARKUP as VK_MARKUP
from platforms.vk.formatting import generate_message as vk_text
from services.game_service import GameService


async def sync_game_publications(game_id: int) -> None:
    """Create/update every configured platform publication without blocking core DB changes."""
    settings = get_settings()
    with SessionLocal() as session:
        service = GameService(session)
        game = service.get_game(game_id=game_id)
        if game is None:
            return
        game_data = {
            "id": game.id,
            "status": game.status,
            "platform": game.chat.platform,
            "chat_id": game.chat_id,
            "starts_at": game.starts_at,
            "description": game.description,
            "duration_minutes": game.duration_minutes,
            "price_per_hour": game.price_per_hour,
            "max_players_count": game.max_players_count,
            "title": game.title,
            "participants": [
                (p.id, p.user_id, p.status, p.display_name_snapshot,
                 [(a.platform, a.platform_user_id) for a in p.user.platform_accounts])
                for p in game.participants
            ],
        }
        destinations = [
            (chat.id, chat.platform, chat.platform_chat_id,
             (publication.message_id if (publication := service.get_publication(game_id=game.id, chat_id=chat.id)) else None))
            for chat in service.list_community_chats(chat_id=game.chat_id)
        ]

    if game_data["status"] != GameStatus.ACTIVE:
        return

    # Use stored game data to format without holding a database session over network calls.
    class Participant:
        def __init__(self, row):
            self.id, self.user_id, self.status, self.display_name_snapshot, accounts = row
            self.user = type("Profile", (), {"platform_accounts": [type("Account", (), {"platform": p, "platform_user_id": uid}) for p, uid in accounts]})()

    game_obj = type("GameView", (), {**{k: v for k, v in game_data.items() if k not in {"participants", "platform", "chat_id", "status", "id"}},
                                      "participants": [Participant(row) for row in game_data["participants"]]})()

    for chat_id, platform, platform_chat_id, message_id in destinations:
        try:
            if platform == Platform.TELEGRAM and settings.telegram_bot_token:
                async with Bot(settings.telegram_bot_token) as bot:
                    markup = TELEGRAM_MARKUP
                    text = telegram_text(game_obj)
                    if message_id:
                        await bot.edit_message_text(
                            chat_id=int(platform_chat_id), message_id=int(message_id),
                            text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN,
                        )
                    else:
                        message = await bot.send_message(
                            chat_id=int(platform_chat_id), text=text,
                            reply_markup=markup, parse_mode=ParseMode.MARKDOWN,
                        )
                        with SessionLocal() as session:
                            GameService(session).add_publication(game_id=game_id, chat_id=chat_id, message_id=str(message.message_id))
            elif platform == Platform.VK and settings.vk_bot_token:
                api = API(settings.vk_bot_token)
                text = vk_text(game_obj)
                if message_id:
                    await api.messages.edit(
                        peer_id=int(platform_chat_id), cmid=int(message_id),
                        message=text, keyboard=VK_MARKUP,
                    )
                else:
                    response = await api.messages.send(
                        peer_id=int(platform_chat_id), message=text,
                        keyboard=VK_MARKUP, random_id=0,
                    )
                    conversation_message_id = response
                    try:
                        result = await api.messages.get_by_id(message_ids=[response])
                        conversation_message_id = result.items[0].conversation_message_id
                    except Exception:
                        pass
                    with SessionLocal() as session:
                        GameService(session).add_publication(game_id=game_id, chat_id=chat_id, message_id=str(conversation_message_id))
        except Exception:
            # A platform outage must not undo a game or signup committed to the database.
            logging.exception("Could not sync game %s to %s chat %s", game_id, platform, platform_chat_id)
            continue


async def delete_game_publications(game_id: int) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        service = GameService(session)
        game = service.get_game(game_id=game_id)
        if game is None:
            return
        destinations = [
            (chat.platform, chat.platform_chat_id, publication.message_id)
            for chat in service.list_community_chats(chat_id=game.chat_id)
            if (publication := service.get_publication(game_id=game_id, chat_id=chat.id)) is not None
        ]
    for platform, chat_id, message_id in destinations:
        try:
            if platform == Platform.TELEGRAM and settings.telegram_bot_token:
                async with Bot(settings.telegram_bot_token) as bot:
                    await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
            elif platform == Platform.VK and settings.vk_bot_token:
                api = API(settings.vk_bot_token)
                await api.messages.delete(peer_id=int(chat_id), cmids=[int(message_id)], delete_for_all=1)
        except Exception:
            logging.exception("Could not delete game %s publication from %s chat %s", game_id, platform, chat_id)
            continue
