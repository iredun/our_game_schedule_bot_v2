import logging
from datetime import datetime

from telegram import Update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import ContextTypes

from core.config import get_settings
from core.game_time import format_game_datetime_range
from db.models import GameParticipantStatus, Platform
from db.session import SessionLocal
from platforms.telegram.access import check_access
from platforms.telegram.consts import REPLY_MARKUP
from platforms.telegram.formatting import generate_message, pretty_user_name
from platforms.telegram.messaging import delete_invoking_command, send_notice
from platforms.telegram.parsing import (
    apply_time_range,
    parse_game_datetime,
    parse_time_range,
)
from services.calendar_service import CalendarService
from services.chat_member_service import ChatMemberService
from services.game_service import GameService
from services.platform_service import PlatformService


settings = get_settings()


async def _can_edit_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    account_id: int,
    author_account_id: int,
) -> bool:
    if account_id == author_account_id:
        return True

    try:
        member = await context.bot.get_chat_member(
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id,
        )
    except Exception:
        return False
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args and context.args[0] == "calendar_link":
        await calendar_link(update, context)
        return

    if update.effective_chat.type != "private" and not await check_access(update, context):
        return

    if update.effective_chat.type == "private":
        await send_notice(
            update,
            context,
            text="Создай игру через веб-интерфейс или получи персональную iCal ссылку.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "Создать игру", web_app=WebAppInfo(url=f"{settings.app_base_url.rstrip('/')}/app")
                )],
                [InlineKeyboardButton(
                    "Список игр", web_app=WebAppInfo(url=f"{settings.app_base_url.rstrip('/')}/games")
                )],
            ]),
        )
    else:
        await send_notice(update, context, text="Бот запущен. Команда /calendar_link создаст персональную iCal ссылку.")


async def calendar_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        me = await context.bot.get_me()
        if me.username:
            await send_notice(
                update,
                context,
                text=(
                    "Перейди в личку бота и запусти генерацию ссылки:\n"
                    f"https://t.me/{me.username}?start=calendar_link"
                ),
            )
        else:
            await send_notice(
                update,
                context,
                text="Напиши боту в личку и вызови /calendar_link.",
            )
        return

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
        session.commit()

        calendar_service = CalendarService(session)
        token, created = calendar_service.get_or_create_token(account.user)
        url = calendar_service.build_calendar_url(token.token)

    title = (
        "Создал новую персональную iCal ссылку:"
        if created
        else "Твоя персональная iCal ссылка:"
    )
    await send_notice(
        update,
        context,
        text=(
            f"{title}\n"
            f"{url}\n\n"
            "Храни ее как пароль: любой, у кого она есть, увидит твои игры."
        ),
    )


async def new_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = await check_access(update, context)
    if not access:
        return

    try:
        date_time = parse_game_datetime(context.args.pop(0))
    except Exception:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            parse_mode=ParseMode.MARKDOWN,
            text="Неверный формат сообщения!\n"
            "Формат: /new ДАТА ТЕКСТ\n"
            "Пример: `/new 10 #игра` (Дата текущего месяца)\n"
            "Пример: `/new 10.10.2023 #игра` (Конкретная дата)\n"
            "Пример: `/new 10.10.2023 19:00-22:00 #игра` (Дата и время)\n"
            "Если хотим установить цену за час, то пишем так:\n"
            "`/new 10.10.2023 #игра ₽1000`",
        )
        return

    if context.args:
        time_arg = None
        for arg in context.args:
            if ":" not in arg or "-" not in arg:
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
                    await send_notice(update, context,
                        chat_id=update.effective_chat.id,
                        reply_to_message_id=update.message.id,
                        parse_mode=ParseMode.MARKDOWN,
                        text="Неверный формат времени!\n"
                        "Используй диапазон в формате `19:00-22:00`.",
                    )
                    return
        if time_arg:
            context.args.remove(time_arg)
        else:
            await send_notice(update, context,
                chat_id=update.effective_chat.id,
                reply_to_message_id=update.message.id,
                parse_mode=ParseMode.MARKDOWN,
                text="Неверный формат времени!\n"
                "Используй диапазон в формате `19:00-22:00`.",
            )
            return

    logging.info("New game - %s %s", date_time, context.args)
    price, user_message = _normalize_new_args(context.args)

    date_text = format_game_datetime_range(date_time, duration_minutes)
    message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=REPLY_MARKUP,
        text=f"{date_text} {user_message}\nСписок участников:\n\n",
    )

    await message.pin()

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
            source_message_id=str(message.message_id),
        )

    await delete_invoking_command(update, context)


async def list_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = await check_access(update, context)
    if not access:
        return

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.TELEGRAM,
            platform_chat_id=str(update.effective_chat.id),
            title=update.effective_chat.title,
        )
        session.commit()

        game_service = GameService(session)
        game_service.cleanup_old_chat_games(
            chat_id=chat.id, before_dt=_now_date_without_time()
        )
        games = game_service.list_chat_games(chat_id=chat.id)

    if not games:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Список игр пуст!",
        )
        return

    for game in games:
        game_text = f"{format_game_datetime_range(game.starts_at, game.duration_minutes)} {game.description or ''}".strip()
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=int(game.source_message_id)
            if game.source_message_id
            else None,
            text=game_text,
        )


async def delete_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = await check_access(update, context)
    if not access:
        return

    if not update.message.reply_to_message:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Нужно ответить на сообщение с игрой!",
        )
        return

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.TELEGRAM,
            platform_chat_id=str(update.effective_chat.id),
            title=update.effective_chat.title,
        )
        account = platform_service.register_account(
            platform=Platform.TELEGRAM,
            platform_user_id=str(update.effective_user.id),
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name,
            display_name=update.effective_user.full_name,
        )
        session.commit()

        game_service = GameService(session)
        game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=str(update.message.reply_to_message.message_id),
        )
        if game is None:
            await send_notice(update, context,
                chat_id=update.effective_chat.id,
                reply_to_message_id=update.message.id,
                text="Игра не найдена!",
            )
            return

        if account.id != game.author_account_id:
            await send_notice(update, context,
                chat_id=update.effective_chat.id,
                reply_to_message_id=update.message.id,
                text="Удалять может только автор!",
            )
            return

        game_service.delete_game(game)

    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.message.reply_to_message.message_id,
    )
    await send_notice(update, context,
        chat_id=update.effective_chat.id,
        reply_to_message_id=update.message.id,
        text="Игра удалена!",
    )


async def mynameis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = await check_access(update, context)
    if not access:
        return

    new_name = " ".join(context.args)

    if not new_name.strip():
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Пожалуйста, введите новое имя!",
        )
        return

    await send_notice(update, context,
        chat_id=update.effective_chat.id,
        reply_to_message_id=update.message.id,
        text=f"Какой ты нахуй {new_name}?, ты  же {update.effective_user.full_name}, не позорься!",
    )


async def _update_game_and_refresh_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    update_fields: dict[str, object],
    success_message: str,
):
    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.TELEGRAM,
            platform_chat_id=str(update.effective_chat.id),
            title=update.effective_chat.title,
        )
        account = platform_service.register_account(
            platform=Platform.TELEGRAM,
            platform_user_id=str(update.effective_user.id),
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name,
            display_name=update.effective_user.full_name,
        )
        session.commit()

        game_service = GameService(session)
        game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=str(update.message.reply_to_message.message_id),
        )
        if game is None:
            return

        if not await _can_edit_game(update, context, account.id, game.author_account_id):
            await send_notice(update, context,
                chat_id=update.effective_chat.id,
                reply_to_message_id=update.message.id,
                text="Редактировать может только автор или админ чата!",
            )
            return

        game = game_service.update_game_settings(game, **update_fields)

        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text=success_message,
        )

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=update.message.reply_to_message.message_id,
            text=generate_message(game),
            reply_markup=REPLY_MARKUP,
            parse_mode=ParseMode.MARKDOWN,
        )


async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = await check_access(update, context)
    if not access:
        return

    if not context.args:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Не указана цена игры!",
        )
        return

    try:
        price = int(context.args[0])
    except Exception:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Неверный формат цены! Введите число.",
        )
        return

    if price <= 0:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Неверный формат цены! Введите число больше 0.",
        )
        return

    await _update_game_and_refresh_message(
        update,
        context,
        update_fields={"price_per_hour": price},
        success_message="Цена игры обновлена!",
    )


async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = await check_access(update, context)
    if not access:
        return

    if not context.args:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Не указан временной диапазон!",
        )
        return

    if not update.message.reply_to_message:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Нужно ответить на сообщение с игрой!",
        )
        return

    try:
        time_range = context.args[0]
        parse_time_range(time_range)
    except Exception:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Неверный формат времени! Используй диапазон вида 19:00-20:30.",
        )
        return

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.TELEGRAM,
            platform_chat_id=str(update.effective_chat.id),
            title=update.effective_chat.title,
        )
        account = platform_service.register_account(
            platform=Platform.TELEGRAM,
            platform_user_id=str(update.effective_user.id),
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name,
            display_name=update.effective_user.full_name,
        )
        session.commit()

        game_service = GameService(session)
        game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=str(update.message.reply_to_message.message_id),
        )
        if game is None:
            await send_notice(update, context,
                chat_id=update.effective_chat.id,
                reply_to_message_id=update.message.id,
                text="Игра не найдена!",
            )
            return

        if not await _can_edit_game(update, context, account.id, game.author_account_id):
            await send_notice(update, context,
                chat_id=update.effective_chat.id,
                reply_to_message_id=update.message.id,
                text="Редактировать может только автор или админ чата!",
            )
            return

        try:
            starts_at, duration_minutes = apply_time_range(game.starts_at, time_range)
        except Exception:
            await send_notice(update, context,
                chat_id=update.effective_chat.id,
                reply_to_message_id=update.message.id,
                text="Неверный формат времени! Используй диапазон вида 19:00-20:30.",
            )
            return

        game = game_service.update_game_settings(
            game,
            starts_at=starts_at,
            duration_minutes=duration_minutes,
        )

        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Время игры обновлено!",
        )

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=update.message.reply_to_message.message_id,
            text=generate_message(game),
            reply_markup=REPLY_MARKUP,
            parse_mode=ParseMode.MARKDOWN,
        )


async def set_max_players_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access = await check_access(update, context)
    if not access:
        return

    if not context.args:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Не указана цена игры!",
        )
        return

    try:
        count = int(context.args[0])
    except Exception:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Неверный формат кол-ва! Введите число.",
        )
        return

    if count <= 0:
        await send_notice(update, context,
            chat_id=update.effective_chat.id,
            reply_to_message_id=update.message.id,
            text="Неверный формат кол-ва! Введите число больше 0.",
        )
        return

    await _update_game_and_refresh_message(
        update,
        context,
        update_fields={"max_players_count": count},
        success_message="Кол-во игроков обновлено!",
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    with SessionLocal() as session:
        platform_service = PlatformService(session)
        chat = platform_service.register_chat(
            platform=Platform.TELEGRAM,
            platform_chat_id=str(update.effective_chat.id),
            title=update.effective_chat.title,
        )
        account = platform_service.register_account(
            platform=Platform.TELEGRAM,
            platform_user_id=str(query.from_user.id),
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            last_name=query.from_user.last_name,
            display_name=query.from_user.full_name,
        )
        session.commit()

        ChatMemberService(session).observe_membership(
            chat_id=chat.id, user_id=account.user_id
        )

        chat_member_service = ChatMemberService(session)
        member_settings = chat_member_service.get_settings(
            chat_id=chat.id, user_id=account.user_id
        )
        display_name = pretty_user_name(
            query.from_user,
            member_settings.custom_display_name if member_settings else "",
        )

        game_service = GameService(session)
        game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=str(query.message.message_id),
        )
        if game is None:
            await query.answer()
            return

        if query.data in {"i", "not_sure"}:
            changed = game_service.set_main_status(
                game_id=game.id,
                user_id=account.user_id,
                status=_status_from_callback(query.data),
                display_name_snapshot=display_name,
            )
            if not changed and query.data == "i":
                await query.answer()
                return
        elif query.data == "i+1":
            game_service.add_participation(
                game_id=game.id,
                user_id=account.user_id,
                status=GameParticipantStatus.PLUS_ONE,
                display_name_snapshot=display_name,
            )
        elif query.data == "i-1":
            deleted = game_service.remove_participation(
                game_id=game.id,
                user_id=account.user_id,
                status=GameParticipantStatus.PLUS_ONE,
            )
            if not deleted:
                await query.answer()
                return
        elif query.data == "not_play":
            deleted = game_service.remove_main_status(
                game_id=game.id,
                user_id=account.user_id,
            )
            if not deleted:
                await query.answer()
                return
        elif query.data == "check_not_sure":
            if account.id != game.author_account_id:
                await query.answer(
                    text="Только автор игры может выполнять это действие",
                    show_alert=True,
                )
                return

            not_sure_users = [
                participant.display_name_snapshot
                for participant in sorted(game.participants, key=lambda item: item.id)
                if participant.status == GameParticipantStatus.MAYBE
            ]
            not_sure_text = "\n".join(filter(None, not_sure_users))

            if not_sure_text:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    reply_to_message_id=query.message.message_id,
                    parse_mode=ParseMode.MARKDOWN,
                    text=f"Решите свои вопросы!\n{not_sure_text}",
                )
            await query.answer()
            return
        else:
            await query.answer()
            return

        refreshed_game = game_service.get_game_by_source_message(
            chat_id=chat.id,
            source_message_id=str(query.message.message_id),
        )
        await query.edit_message_text(
            text=generate_message(refreshed_game),
            reply_markup=REPLY_MARKUP,
            parse_mode=ParseMode.MARKDOWN,
        )
        await query.answer()
