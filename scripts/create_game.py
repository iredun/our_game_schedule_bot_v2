"""Create and publish a Telegram game from a shell or cron job."""

import argparse
import asyncio
from datetime import date, datetime, time, timedelta

from telegram import Bot

from core.config import get_settings
from db.models import Platform
from db.session import SessionLocal
from platforms.telegram.consts import REPLY_MARKUP
from platforms.telegram.formatting import generate_message
from services.game_service import GameService
from services.platform_service import PlatformService


WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6
}


def resolve_date(expression: str, today: date) -> date:
    """Resolve YYYY-MM-DD, today, tomorrow, or this:/next:<weekday>."""
    value = expression.strip().lower()
    if value == "today":
        return today
    if value == "tomorrow":
        return today + timedelta(days=1)
    if ":" in value:
        mode, weekday = value.split(":", 1)
        if mode not in {"this", "next"} or weekday not in WEEKDAYS:
            raise ValueError("Формула даты должна быть this:<день> или next:<день>.")
        offset = (WEEKDAYS[weekday] - today.weekday()) % 7
        if mode == "next" and offset == 0:
            offset = 7
        return today + timedelta(days=offset)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Дата: YYYY-MM-DD, today, tomorrow, this:saturday или next:saturday.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создать игру и опубликовать её в Telegram.")
    parser.add_argument("--chat-id", required=True, type=int, help="ID Telegram группы/чата")
    parser.add_argument("--author-id", required=True, type=int, help="Telegram user ID автора игры")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD, today, tomorrow, this:<weekday>, next:<weekday>")
    parser.add_argument("--time", required=True, help="Время начала, например 19:00")
    parser.add_argument("--title", default="#игра", help="Заголовок игры")
    parser.add_argument("--description", default="", help="Описание игры")
    parser.add_argument("--duration", type=int, help="Длительность в минутах")
    parser.add_argument("--price", type=int, help="Цена за час")
    parser.add_argument("--max-players", type=int, help="Максимум игроков")
    return parser.parse_args()


async def create_and_publish(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise ValueError("Не задан TELEGRAM_BOT_TOKEN.")
    game_date = resolve_date(args.date, datetime.now(settings.timezone).date())
    try:
        game_time = time.fromisoformat(args.time)
    except ValueError as exc:
        raise ValueError("Время нужно указать в формате HH:MM.") from exc
    if args.duration is not None and args.duration <= 0:
        raise ValueError("Длительность должна быть больше нуля.")
    if args.price is not None and args.price <= 0:
        raise ValueError("Цена должна быть больше нуля.")
    if args.max_players is not None and args.max_players <= 0:
        raise ValueError("Максимум игроков должен быть больше нуля.")

    starts_at = datetime.combine(game_date, game_time, tzinfo=settings.timezone)
    description = args.description.strip()
    title = args.title.strip() or "#игра"
    async with Bot(settings.telegram_bot_token) as bot:
        sent_message = await bot.send_message(
            chat_id=args.chat_id,
            text=f"{starts_at.strftime('%d.%m.%Y %H:%M')} {description}\nСписок участников:\n\n",
            reply_markup=REPLY_MARKUP,
        )
        try:
            await bot.pin_chat_message(chat_id=args.chat_id, message_id=sent_message.message_id)
        except Exception:
            # Pinning is optional; publication and persistence should still succeed.
            pass

        with SessionLocal() as session:
            platform_service = PlatformService(session)
            account = platform_service.register_account(
                platform=Platform.TELEGRAM,
                platform_user_id=str(args.author_id),
            )
            chat = platform_service.register_chat(
                platform=Platform.TELEGRAM,
                platform_chat_id=str(args.chat_id),
                title=sent_message.chat.title,
            )
            session.commit()
            game = GameService(session).create_game(
                chat_id=chat.id,
                author_account_id=account.id,
                title=title,
                description=description or None,
                starts_at=starts_at,
                duration_minutes=args.duration,
                price_per_hour=args.price,
                max_players_count=args.max_players,
                source_message_id=str(sent_message.message_id),
            )
            game = GameService(session).get_game(game_id=game.id)
            await bot.edit_message_text(
                chat_id=args.chat_id,
                message_id=sent_message.message_id,
                text=generate_message(game),
                reply_markup=REPLY_MARKUP,
                parse_mode="Markdown",
            )
    print(f"Игра {game.id} опубликована: {starts_at.isoformat()} (message_id={sent_message.message_id})")
    return game.id


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(create_and_publish(args))
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
