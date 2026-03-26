import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from vkbottle import GroupEventType
from vkbottle.bot import Bot, Message, MessageEvent

from core.config import get_settings
from core.game_time import format_game_datetime_range
from db.models import GameParticipantStatus, Platform
from db.session import SessionLocal
from platforms.telegram.parsing import apply_time_range, parse_game_datetime, parse_time_range
from platforms.vk.access import check_access
from platforms.vk.consts import REPLY_MARKUP
from platforms.vk.formatting import generate_message, pretty_user_name
from services.calendar_service import CalendarService
from services.chat_member_service import ChatMemberService
from services.game_service import GameService
from services.platform_service import PlatformService


settings = get_settings()


def register_handlers(bot: Bot) -> None:
    @bot.on.message()
    async def handle_message(message: Message) -> None:
        await route_message(message)

    @bot.on.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=MessageEvent)
    async def handle_message_event(event: MessageEvent) -> None:
        await buttons(bot, event)


def _now_date_without_time() -> datetime:
    return datetime.now(tz=settings.timezone).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _normalize_new_args(args: list[str]) -> tuple[int, str]:
    price = settings.default_game_price
    filtered_args: list[str] = []

    for arg in args:
        if arg.startswith("₽"):
            try:
                parsed_price = int(arg[1:])
                if parsed_price > 0:
                    price = parsed_price
            except Exception:
                pass
            continue

        filtered_args.append(arg)

    return price, " ".join(filtered_args)


def _status_from_callback(data: str) -> GameParticipantStatus:
    mapping = {
        "i": GameParticipantStatus.GOING,
        "not_sure": GameParticipantStatus.MAYBE,
        "i+1": GameParticipantStatus.PLUS_ONE,
    }
    return mapping[data]


def _extract_args(message: Message) -> tuple[str, list[str]]:
    parts = (message.text or "").strip().split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


def _is_private_message(message: Message) -> bool:
    return message.peer_id == message.from_id


def _resolve_message_value(message: Message, attr_name: str, fallback=None):
    value = getattr(message, attr_name, None)
    if callable(value):
        try:
            value = value()
        except TypeError:
            value = None
    return fallback if value is None else value


def _chat_title(message: Message) -> str:
    if getattr(message, "chat_title", None):
        return message.chat_title
    return f"VK chat {message.peer_id}"


def _reply_source_message_id(message: Message) -> str | None:
    reply_message = getattr(message, "reply_message", None)
    if reply_message is None:
        return None

    reply_id = getattr(reply_message, "message_id", None)
    if callable(reply_id):
        try:
            reply_id = reply_id()
        except TypeError:
            reply_id = None
    if reply_id is None:
        reply_id = getattr(reply_message, "id", None)
    if reply_id is not None:
        return str(reply_id)

    reply_cmid = getattr(reply_message, "conversation_message_id", None)
    if reply_cmid is not None:
        return str(reply_cmid)

    return None


async def _message_vk_user(message: Message):
    return await message.get_user()


def _user_display_name(user, fallback_user_id: int) -> str:
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)
    return " ".join(filter(None, [first_name, last_name])) or str(fallback_user_id)


async def _register_message_account(session, message: Message):
    user = await _message_vk_user(message)
    platform_service = PlatformService(session)
    return platform_service.register_account(
        platform=Platform.VK,
        platform_user_id=str(message.from_id),
        first_name=getattr(user, "first_name", None),
        last_name=getattr(user, "last_name", None),
        display_name=_user_display_name(user, message.from_id),
    )


async def _get_conversation_message_id(message: Message, sent_message_id: int) -> str:
    messages = await message.ctx_api.messages.get_by_id(message_ids=[sent_message_id])
    items = getattr(messages, "items", None) or []
    sent_message = items[0] if items else None
    conversation_message_id = getattr(sent_message, "conversation_message_id", None)
    if conversation_message_id is not None:
        return str(conversation_message_id)
    return str(sent_message_id)


async def route_message(message: Message) -> None:
    command, args = _extract_args(message)
    handlers = {
        "/start": start,
        "/calendar_link": calendar_link,
        "/new": new_schedule,
        "/list": list_schedule,
        "/delete": delete_schedule,
        "/mynameis": mynameis,
        "/price": set_price,
        "/set_time": set_time,
        "/max_players_count": set_max_players_count,
    }

    handler = handlers.get(command)
    if handler is None:
        return

    await handler(message, args)


async def start(message: Message, args: list[str]) -> None:
    if args and args[0] == "calendar_link":
        await calendar_link(message, args[1:])
        return

    await message.answer("Бот запущен. Команда /calendar_link создаст персональную iCal ссылку.")


async def calendar_link(message: Message, args: list[str]) -> None:
    if not _is_private_message(message):
        await message.answer("Открой диалог с ботом в личке и вызови /calendar_link.")
        return

    with SessionLocal() as session:
        account = await _register_message_account(session, message)
        session.commit()

        calendar_service = CalendarService(session)
        token, created = calendar_service.get_or_create_token(account.user)
        url = calendar_service.build_calendar_url(token.token)

    title = "Создал новую персональную iCal ссылку:" if created else "Твоя персональная iCal ссылка:"
    await message.answer(
        f"{title}\n"
        f"{url}\n\n"
        "Храни ее как пароль: любой, у кого она есть, увидит твои игры."
    )


async def new_schedule(message: Message, args: list[str]) -> None:
    access = await check_access(message)
    if not access:
        return

    if not args:
        await message.answer(
            "Неверный формат сообщения!\n"
            "Формат: /new ДАТА ТЕКСТ\n"
            "Пример: /new 10 #игра\n"
            "Пример: /new 10.10.2026 #игра\n"
            "Пример: /new 10.10.2026 19:00-22:00 #игра\n"
            "Дополнительно: /new 10.10.2026 #игра ₽1000"
        )
        return

    try:
        date_time = parse_game_datetime(args[0])
    except Exception:
        await message.answer(
            "Неверный формат сообщения!\n"
            "Формат: /new ДАТА ТЕКСТ\n"
            "Пример: /new 10 #игра\n"
            "Пример: /new 10.10.2026 #игра\n"
            "Пример: /new 10.10.2026 19:00-22:00 #игра\n"
            "Дополнительно: /new 10.10.2026 #игра ₽1000"
        )
        return

    parsed_duration_minutes: int | None = None
    if len(args) > 1:
        time_arg = None
        for arg in args[1:]:
            if not ":" in arg or not "-" in arg:
                continue
            try:
                parse_time_range(arg)
            except Exception:
                pass
            else:
                try:
                    date_time, duration_minutes = apply_time_range(date_time, arg)
                    time_arg = arg
                    break
                except Exception:
                    await message.answer(
                        "Неверный формат времени!\n"
                        "Используй диапазон в формате 19:00-22:00."
                    )
                    return
        if time_arg:
            args.remove(time_arg)
        else:
            await message.answer(
                "Неверный формат времени!\n"
                "Используй диапазон в формате 19:00-22:00."
            )
            return

    logging.info("New VK game - %s %s", date_time, args[1:])
    price, user_message = _normalize_new_args(args[1:])

    date_text = format_game_datetime_range(date_time, duration_minutes)
    sent_message_id = await message.ctx_api.messages.send(
        peer_id=message.peer_id,
        message=f"{date_text} {user_message}\nСписок участников:\n\n",
        keyboard=REPLY_MARKUP,
        random_id=0,
    )
    source_message_id = await _get_conversation_message_id(message, sent_message_id)

    with SessionLocal() as session:
        account = await _register_message_account(session, message)
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.VK,
            platform_chat_id=str(message.peer_id),
            title=_chat_title(message),
        )
        session.commit()

        game_service = GameService(session)
        game_service.create_game(
            chat_id=chat.id,
            author_account_id=account.id,
            title=user_message or "#игра",
            description=user_message,
            starts_at=date_time,
            duration_minutes=duration_minutes,
            price_per_hour=price,
            max_players_count=settings.default_max_players_count,
            source_message_id=source_message_id,
        )


async def list_schedule(message: Message, args: list[str]) -> None:
    access = await check_access(message)
    if not access:
        return

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.VK,
            platform_chat_id=str(message.peer_id),
            title=_chat_title(message),
        )
        session.commit()

        game_service = GameService(session)
        game_service.cleanup_old_chat_games(chat_id=chat.id, before_dt=_now_date_without_time())
        games = game_service.list_chat_games(chat_id=chat.id)

    if not games:
        await message.answer("Список игр пуст!")
        return

    for game in games:
        await message.answer(
            f"{format_game_datetime_range(game.starts_at, game.duration_minutes)} {game.description or ''}".strip()
        )


async def delete_schedule(message: Message, args: list[str]) -> None:
    access = await check_access(message)
    if not access:
        return

    reply_source_message_id = _reply_source_message_id(message)
    if reply_source_message_id is None:
        await message.answer("Нужно ответить на сообщение с игрой!")
        return

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.VK,
            platform_chat_id=str(message.peer_id),
            title=_chat_title(message),
        )
        account = await _register_message_account(session, message)
        session.commit()

        game_service = GameService(session)
        game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=reply_source_message_id,
        )
        if game is None:
            await message.answer("Игра не найдена(del)!")
            return

        if account.id != game.author_account_id:
            await message.answer("Удалять может только автор!")
            return

        game_service.delete_game(game)

    delete_kwargs = {"delete_for_all": 1}
    if _resolve_message_value(getattr(message, "reply_message", None), "message_id") is not None or getattr(
        getattr(message, "reply_message", None), "id", None
    ) is not None:
        delete_kwargs["message_ids"] = [int(reply_source_message_id)]
    else:
        delete_kwargs["peer_id"] = message.peer_id
        delete_kwargs["cmids"] = [int(reply_source_message_id)]

    await message.ctx_api.messages.delete(**delete_kwargs)
    await message.answer("Игра удалена!")


async def mynameis(message: Message, args: list[str]) -> None:
    access = await check_access(message)
    if not access:
        return

    with SessionLocal() as session:
        account = await _register_message_account(session, message)
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.VK,
            platform_chat_id=str(message.peer_id),
            title=_chat_title(message),
        )
        session.commit()

        chat_member_service = ChatMemberService(session)
        if args:
            new_name = " ".join(args)
            chat_member_service.set_custom_name(
                chat_id=chat.id,
                user_id=account.user_id,
                custom_display_name=new_name,
            )
            await message.answer(f"Теперь ты - {new_name}")
        else:
            deleted = chat_member_service.clear_custom_name(
                chat_id=chat.id,
                user_id=account.user_id,
            )
            if deleted:
                await message.answer("Вернул твое настоящее имя!")


async def _update_game_and_refresh_message(
    message: Message,
    *,
    update_fields: dict[str, object],
    success_message: str,
) -> None:
    reply_source_message_id = _reply_source_message_id(message)
    if reply_source_message_id is None:
        await message.answer("Нужно ответить на сообщение с игрой!")
        return

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.VK,
            platform_chat_id=str(message.peer_id),
            title=_chat_title(message),
        )
        account = await _register_message_account(session, message)
        session.commit()

        game_service = GameService(session)
        game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=reply_source_message_id,
        )
        if game is None:
            await message.answer("Игра не найдена(upd_ref)!")
            return

        if account.id != game.author_account_id:
            await message.answer("Редактировать может только автор!")
            return

        game = game_service.update_game_settings(game, **update_fields)

        await message.answer(success_message)

        edit_kwargs = {
            "message": generate_message(game),
            "keyboard": REPLY_MARKUP,
        }
        if _resolve_message_value(getattr(message, "reply_message", None), "message_id") is not None or getattr(
            getattr(message, "reply_message", None), "id", None
        ) is not None:
            edit_kwargs["message_id"] = int(reply_source_message_id)
        else:
            edit_kwargs["peer_id"] = message.peer_id
            edit_kwargs["cmid"] = int(reply_source_message_id)

        await message.ctx_api.messages.edit(**edit_kwargs)


async def set_price(message: Message, args: list[str]) -> None:
    access = await check_access(message)
    if not access:
        return

    if not args:
        await message.answer("Не указана цена игры!")
        return

    try:
        price = int(args[0])
    except Exception:
        await message.answer("Неверный формат цены! Введите число.")
        return

    if price <= 0:
        await message.answer("Неверный формат цены! Введите число больше 0.")
        return

    await _update_game_and_refresh_message(
        message,
        update_fields={"price_per_hour": price},
        success_message="Цена игры обновлена!",
    )


async def set_time(message: Message, args: list[str]) -> None:
    access = await check_access(message)
    if not access:
        return

    if not args:
        await message.answer("Не указан временной диапазон!")
        return

    try:
        time_range = args[0]
        parse_time_range(time_range)
    except Exception:
        await message.answer("Неверный формат времени! Используй диапазон вида 19:00-20:30.")
        return

    reply_source_message_id = _reply_source_message_id(message)
    if reply_source_message_id is None:
        await message.answer("Нужно ответить на сообщение с игрой!")
        return

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.VK,
            platform_chat_id=str(message.peer_id),
            title=_chat_title(message),
        )
        account = await _register_message_account(session, message)
        session.commit()

        game_service = GameService(session)
        game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=reply_source_message_id,
        )
        if game is None:
            await message.answer("Игра не найдена!")
            return

        if account.id != game.author_account_id:
            await message.answer("Редактировать может только автор!")
            return

        try:
            starts_at, duration_minutes = apply_time_range(game.starts_at, time_range)
        except Exception:
            await message.answer("Неверный формат времени! Используй диапазон вида 19:00-20:30.")
            return

        game = game_service.update_game_settings(
            game,
            starts_at=starts_at,
            duration_minutes=duration_minutes,
        )

        await message.answer("Время игры обновлено!")

        edit_kwargs = {
            "message": generate_message(game),
            "keyboard": REPLY_MARKUP,
        }
        if _resolve_message_value(getattr(message, "reply_message", None), "message_id") is not None or getattr(
            getattr(message, "reply_message", None), "id", None
        ) is not None:
            edit_kwargs["message_id"] = int(reply_source_message_id)
        else:
            edit_kwargs["peer_id"] = message.peer_id
            edit_kwargs["cmid"] = int(reply_source_message_id)

        await message.ctx_api.messages.edit(**edit_kwargs)


async def set_max_players_count(message: Message, args: list[str]) -> None:
    access = await check_access(message)
    if not access:
        return

    if not args:
        await message.answer("Не указано кол-во игроков!")
        return

    try:
        count = int(args[0])
    except Exception:
        await message.answer("Неверный формат кол-ва! Введите число.")
        return

    if count <= 0:
        await message.answer("Неверный формат кол-ва! Введите число больше 0.")
        return

    await _update_game_and_refresh_message(
        message,
        update_fields={"max_players_count": count},
        success_message="Кол-во игроков обновлено!",
    )


async def buttons(bot: Bot, event: MessageEvent) -> None:
    payload = getattr(event, "payload", None) or {}
    command = payload.get("cmd")
    if command is None:
        await event.show_snackbar("Неизвестное действие")
        return

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.VK,
            platform_chat_id=str(event.peer_id),
            title=f"VK chat {event.peer_id}",
        )
        users = await bot.api.users.get(user_ids=[event.user_id])
        user = users[0] if users else None
        account = platform_service.register_account(
            platform=Platform.VK,
            platform_user_id=str(event.user_id),
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
            display_name=_user_display_name(user, event.user_id),
        )
        session.commit()

        chat_member_service = ChatMemberService(session)
        member_settings = chat_member_service.get_settings(chat_id=chat.id, user_id=account.user_id)
        display_name = pretty_user_name(
            user_id=event.user_id,
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
            custom_name=member_settings.custom_display_name if member_settings else "",
        )

        source_message_id = str(event.conversation_message_id)

        game_service = GameService(session)
        game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=source_message_id,
        )

        if game is None:
            await event.show_snackbar("Игра не найдена (btn)")
            return

        if command in {"i", "not_sure"}:
            changed = game_service.set_main_status(
                game_id=game.id,
                user_id=account.user_id,
                status=_status_from_callback(command),
                display_name_snapshot=display_name,
            )
            if not changed and command == "i":
                await event.show_snackbar("Ты уже отмечен")
                return
        elif command == "i+1":
            game_service.add_participation(
                game_id=game.id,
                user_id=account.user_id,
                status=GameParticipantStatus.PLUS_ONE,
                display_name_snapshot=display_name,
            )
        elif command == "i-1":
            deleted = game_service.remove_participation(
                game_id=game.id,
                user_id=account.user_id,
                status=GameParticipantStatus.PLUS_ONE,
            )
            if not deleted:
                await event.show_snackbar("Лишнего +1 нет")
                return
        elif command == "not_play":
            deleted = game_service.remove_main_status(
                game_id=game.id,
                user_id=account.user_id,
            )
            if not deleted:
                await event.show_snackbar("Ты не отмечен в списке")
                return
        elif command == "check_not_sure":
            if account.id != game.author_account_id:
                await event.show_snackbar("Только автор игры может выполнять это действие")
                return

            not_sure_users = [
                participant.display_name_snapshot
                for participant in sorted(game.participants, key=lambda item: item.id)
                if participant.status == GameParticipantStatus.MAYBE
            ]
            not_sure_text = "\n".join(filter(None, not_sure_users))

            if not_sure_text:
                await bot.api.messages.send(
                    peer_id=event.peer_id,
                    message=f"Решите свои вопросы!\n{not_sure_text}",
                    random_id=0,
                )
            await event.show_snackbar("Готово")
            return
        else:
            await event.show_snackbar("Неизвестное действие")
            return

        refreshed_game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=source_message_id,
        )
        edit_kwargs = {
            "message": generate_message(refreshed_game),
            "keyboard": REPLY_MARKUP,
            "peer_id": event.peer_id,
            "cmid": int(source_message_id),
        }

        await bot.api.messages.edit(**edit_kwargs)
        await event.show_snackbar("Обновлено")
