import math
import re

from telegram import User

from core.game_time import calculate_total_price, format_duration_minutes, format_game_datetime_range
from db.models import Game, GameParticipantStatus, Platform
from platforms.telegram.consts import TYPE_TEXT_ADD
from core.config import get_settings


settings = get_settings()


def pretty_user_name(user: User, custom_name: str = "") -> str:
    if custom_name:
        return f"[{custom_name}](tg://user?id={user.id})"

    user_full_name = " ".join(
        part.strip() if part else ""
        for part in [user.first_name, user.last_name]
    ).strip()

    if not user_full_name:
        user_full_name = f"@{user.username}"

    return f"[{user_full_name}](tg://user?id={user.id})"


def _participant_sort_key(participant) -> int:
    return participant.id


def _participant_type_text(status: GameParticipantStatus) -> str:
    mapping = {
        GameParticipantStatus.GOING: TYPE_TEXT_ADD["i"],
        GameParticipantStatus.PLUS_ONE: TYPE_TEXT_ADD["i+1"],
        GameParticipantStatus.MAYBE: TYPE_TEXT_ADD["not_sure"],
    }
    return mapping[status]


def generate_message(game: Game) -> str:
    total_price = calculate_total_price(game.price_per_hour, game.duration_minutes)
    participants = sorted(game.participants, key=_participant_sort_key)
    total_users = len(participants)

    try:
        users_count = game.max_players_count if total_users > game.max_players_count else total_users
        price_per_user = math.ceil(total_price / users_count)
    except Exception:
        price_per_user = 0

    users_numeric_list: list[str] = []
    for index, participant in enumerate(participants, 1):
        account = next(iter(participant.user.platform_accounts), None)
        snapshot = participant.display_name_snapshot or f"user-{participant.user_id}"
        if account and account.platform == Platform.TELEGRAM:
            match = re.fullmatch(r"\[(.*)\]\(tg://user\?id=\d+\)", snapshot)
            display_name = f"[{match.group(1) if match else snapshot}](tg://user?id={account.platform_user_id})"
        else:
            match = re.fullmatch(r"\[id\d+\|(.*)\]", snapshot)
            display_name = f"{match.group(1) if match else snapshot} 🔵 VK"
        users_numeric_list.append(
            f"{index}. {display_name}{_participant_type_text(participant.status)}"
        )
        if index == game.max_players_count and total_users > game.max_players_count:
            users_numeric_list.append("--- Запасной список ---")

    users_text = "\n".join(users_numeric_list)
    date_text = format_game_datetime_range(game.starts_at, game.duration_minutes)
    description = game.description or ""

    return (
        f"{date_text} {description}\n"
        f"Список участников:\n"
        f"{users_text}"
        f"\n------\n"
        f"Цена за час: `{game.price_per_hour}₽`\n"
        f"Продолжительность игры: `{format_duration_minutes(game.duration_minutes)}`\n"
        f"Стоимость игры: `{total_price}₽`\n"
        f"С одного игрока: `{price_per_user}₽`"
    )
