import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from telegram import Bot
from telegram.constants import ChatMemberStatus, ParseMode

from core.config import get_settings
from db.models import GameStatus, Platform
from db.session import get_session
from platforms.telegram.consts import REPLY_MARKUP
from platforms.telegram.formatting import generate_message
from services.chat_member_service import ChatMemberService
from services.game_service import GameService
from services.platform_service import PlatformService


router = APIRouter(prefix="/api/telegram", tags=["telegram"])
settings = get_settings()


class CreateGameRequest(BaseModel):
    chat_id: int
    starts_at: datetime
    description: str = Field(default="#игра", max_length=1000)
    duration_minutes: int = Field(default=120, ge=30, le=720)
    price_per_hour: int = Field(default=2000, ge=0, le=1_000_000)
    max_players_count: int = Field(default=14, ge=1, le=100)


class UpdateGameRequest(BaseModel):
    starts_at: datetime
    description: str = Field(max_length=1000)
    duration_minutes: int = Field(ge=30, le=720)
    price_per_hour: int = Field(ge=0, le=1_000_000)
    max_players_count: int = Field(ge=1, le=100)


def _telegram_user(init_data: str) -> dict:
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram is not configured")
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash")
        auth_date = int(pairs["auth_date"])
        if abs(time.time() - auth_date) > 86400:
            raise ValueError("expired initData")
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            raise ValueError("invalid hash")
        user = json.loads(pairs["user"])
        if not isinstance(user.get("id"), int):
            raise ValueError("invalid user")
        return user
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid or expired Telegram initData")


def _require_user(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Telegram initData required")
    return _telegram_user(authorization[4:])


def _register_account(session: Session, user: dict):
    service = PlatformService(session)
    return service.register_account(
        platform=Platform.TELEGRAM,
        platform_user_id=str(user["id"]),
        username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        display_name=" ".join(filter(None, [user.get("first_name"), user.get("last_name")])),
    )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=settings.timezone)
    return value.astimezone(settings.timezone)


def _datetime_iso(value: datetime) -> str:
    return _normalize_datetime(value).isoformat()


async def _is_chat_member(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        } or (member.status == ChatMemberStatus.RESTRICTED and member.is_member)
    except Exception:
        return False


async def _is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except Exception:
        return False
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}


def _build_message_url(chat, message_id: str | int | None) -> str | None:
    if not message_id:
        return None
    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"
    chat_id_text = str(chat.id)
    if chat.type in {"supergroup", "channel"} and chat_id_text.startswith("-100"):
        return f"https://t.me/c/{chat_id_text[4:]}/{message_id}"
    return None


async def _message_url(bot: Bot, chat_id: int, message_id: str | int | None) -> str | None:
    if not message_id:
        return None
    try:
        chat = await bot.get_chat(chat_id)
    except Exception:
        return None
    return _build_message_url(chat, message_id)


def _require_game_membership(session: Session, user: dict, chat_id: int):
    account = _register_account(session, user)
    membership = next(
        (
            item
            for item in ChatMemberService(session).list_memberships(user_id=account.user_id)
            if item.chat.platform == Platform.TELEGRAM
            and int(item.chat.platform_chat_id) == chat_id
        ),
        None,
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Нет доступа к этому чату")
    return account, membership


def _active_game_or_404(session: Session, game_id: int):
    game = GameService(session).get_game(game_id=game_id)
    if game is None or game.status != GameStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="Игра не найдена или уже закрыта")
    starts_at = game.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=settings.timezone)
    if starts_at + timedelta(minutes=game.duration_minutes) <= datetime.now(settings.timezone):
        raise HTTPException(status_code=404, detail="Игра уже завершилась")
    return game


@router.get("/chats")
async def list_chats(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    user = _require_user(authorization)
    account = _register_account(session, user)
    session.commit()
    memberships = ChatMemberService(session).list_memberships(user_id=account.user_id)
    result = []
    async with Bot(settings.telegram_bot_token) as bot:
        for membership in memberships:
            chat = membership.chat
            if chat.platform != Platform.TELEGRAM:
                continue
            chat_id = int(chat.platform_chat_id)
            if await _is_chat_member(bot, chat_id, user["id"]):
                result.append({"id": chat_id, "title": chat.title or str(chat_id)})
    return {"chats": result}


@router.post("/games", status_code=201)
async def create_game(
    payload: CreateGameRequest,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    user = _require_user(authorization)
    starts_at = _normalize_datetime(payload.starts_at)
    if starts_at <= datetime.now(settings.timezone):
        raise HTTPException(status_code=422, detail="Дата игры должна быть в будущем")

    account = _register_account(session, user)
    membership = next(
        (
            item
            for item in ChatMemberService(session).list_memberships(user_id=account.user_id)
            if item.chat.platform == Platform.TELEGRAM
            and int(item.chat.platform_chat_id) == payload.chat_id
        ),
        None,
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Нет доступа к этому чату")

    game = None
    message_url = None
    try:
        async with Bot(settings.telegram_bot_token) as bot:
            if not await _is_chat_member(bot, payload.chat_id, user["id"]):
                raise HTTPException(status_code=403, detail="Пользователь больше не состоит в этом чате")
            description = payload.description.strip()
            game = GameService(session).create_game(
                chat_id=membership.chat_id,
                author_account_id=account.id,
                title=(description or "#игра")[:255],
                description=description or None,
                starts_at=starts_at,
                duration_minutes=payload.duration_minutes,
                price_per_hour=payload.price_per_hour,
                max_players_count=payload.max_players_count,
            )
            message = await bot.send_message(
                chat_id=payload.chat_id,
                text=generate_message(game),
                reply_markup=REPLY_MARKUP,
                parse_mode=ParseMode.MARKDOWN,
            )
            game.source_message_id = str(message.message_id)
            session.commit()
            try:
                await message.pin()
            except Exception:
                pass
            message_url = await _message_url(bot, payload.chat_id, message.message_id)
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        if game is not None:
            GameService(session).delete_game(game)
        raise HTTPException(status_code=502, detail="Не удалось отправить игру в чат") from exc

    return {"game_id": game.id, "message_id": message.message_id, "message_url": message_url}


@router.get("/games")
async def list_games(
    chat_id: int = Query(...),
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    user = _require_user(authorization)
    account, membership = _require_game_membership(session, user, chat_id)
    now = datetime.now(settings.timezone)
    games = GameService(session).list_current_chat_games(chat_id=membership.chat_id, from_dt=now)
    async with Bot(settings.telegram_bot_token) as bot:
        if not await _is_chat_member(bot, chat_id, user["id"]):
            raise HTTPException(status_code=403, detail="Пользователь больше не состоит в этом чате")
        is_admin = await _is_chat_admin(bot, chat_id, user["id"])
        try:
            telegram_chat = await bot.get_chat(chat_id)
        except Exception:
            telegram_chat = None
        chat_message_urls = {
            game.id: _build_message_url(telegram_chat, game.source_message_id)
            for game in games
        } if telegram_chat else {}

    return {
        "games": [
            {
                "id": game.id,
                "starts_at": _datetime_iso(game.starts_at),
                "description": game.description or "",
                "duration_minutes": game.duration_minutes,
                "price_per_hour": game.price_per_hour,
                "max_players_count": game.max_players_count,
                "can_edit": game.author_account_id == account.id or is_admin,
                "message_url": chat_message_urls.get(game.id),
            }
            for game in games
        ]
    }


@router.get("/games/{game_id}")
async def get_game_for_edit(
    game_id: int,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    user = _require_user(authorization)
    game = _active_game_or_404(session, game_id)
    chat_id = int(game.chat.platform_chat_id)
    account = _register_account(session, user)
    session.commit()
    async with Bot(settings.telegram_bot_token) as bot:
        if not await _is_chat_member(bot, chat_id, user["id"]):
            raise HTTPException(status_code=403, detail="Пользователь больше не состоит в этом чате")
        can_edit = game.author_account_id == account.id or await _is_chat_admin(
            bot, chat_id, user["id"]
        )
        message_url = await _message_url(bot, chat_id, game.source_message_id)
    if not can_edit:
        raise HTTPException(status_code=403, detail="Редактировать может только автор или админ чата")
    return {
        "id": game.id,
        "chat_id": int(game.chat.platform_chat_id),
        "starts_at": _datetime_iso(game.starts_at),
        "description": game.description or "",
        "duration_minutes": game.duration_minutes,
        "price_per_hour": game.price_per_hour,
        "max_players_count": game.max_players_count,
        "message_url": message_url,
    }


@router.patch("/games/{game_id}")
async def update_game(
    game_id: int,
    payload: UpdateGameRequest,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    user = _require_user(authorization)
    starts_at = _normalize_datetime(payload.starts_at)
    game = _active_game_or_404(session, game_id)
    if starts_at <= datetime.now(settings.timezone) and starts_at != _normalize_datetime(game.starts_at):
        raise HTTPException(status_code=422, detail="Нельзя перенести игру в прошлое")
    chat_id = int(game.chat.platform_chat_id)
    account = _register_account(session, user)
    async with Bot(settings.telegram_bot_token) as bot:
        if not await _is_chat_member(bot, chat_id, user["id"]):
            raise HTTPException(status_code=403, detail="Пользователь больше не состоит в этом чате")
        if game.author_account_id != account.id and not await _is_chat_admin(bot, chat_id, user["id"]):
            raise HTTPException(status_code=403, detail="Редактировать может только автор или админ чата")
        if not game.source_message_id:
            raise HTTPException(status_code=409, detail="У игры нет связанного сообщения в Telegram")

        description = payload.description.strip()
        service = GameService(session)
        service.update_game_settings(
            game,
            starts_at=starts_at,
            description=description,
            title=(description or "#игра")[:255],
            duration_minutes=payload.duration_minutes,
            price_per_hour=payload.price_per_hour,
            max_players_count=payload.max_players_count,
            commit=False,
        )
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(game.source_message_id),
                text=generate_message(game),
                reply_markup=REPLY_MARKUP,
                parse_mode=ParseMode.MARKDOWN,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            raise HTTPException(status_code=502, detail="Не удалось обновить сообщение игры в Telegram") from exc
    return {"id": game.id, "updated": True}
