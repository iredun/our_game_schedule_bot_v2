from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from core.config import get_settings
from db.models import CalendarToken, Game, Platform, UserProfile
from platforms.telegram.formatting import generate_message as generate_telegram_message
from platforms.vk.formatting import generate_message as generate_vk_message
from repositories.calendar_repository import CalendarRepository
from repositories.game_repository import GameRepository


settings = get_settings()


def _escape_ical_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\n", r"\n")
    )


class CalendarService:
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()
        self.calendar_repository = CalendarRepository(session)
        self.game_repository = GameRepository(session)

    def get_or_create_token(self, user: UserProfile) -> tuple[CalendarToken, bool]:
        token = self.calendar_repository.get_active_token(user.id)
        if token is None:
            token = CalendarToken(user_id=user.id)
            self.session.add(token)
            self.session.commit()
            self.session.refresh(token)
            return token, True
        return token, False

    def build_calendar_url(self, token: str) -> str:
        return f"{self.settings.app_base_url.rstrip('/')}/calendar/{token}.ics"

    def get_games_by_token(self, token: str) -> tuple[CalendarToken | None, list[Game]]:
        calendar_token = self.calendar_repository.get_by_token(token)
        if calendar_token is None:
            return None, []

        games = self.game_repository.get_active_games_for_user(
            user_id=calendar_token.user_id,
            from_dt=datetime.now(tz=settings.timezone) - timedelta(days=1),
        )
        self.calendar_repository.touch(calendar_token)
        self.session.commit()
        return calendar_token, games

    def _build_game_description(self, game: Game) -> str:
        if game.chat and game.chat.platform == Platform.TELEGRAM:
            return generate_telegram_message(game)
        if game.chat and game.chat.platform == Platform.VK:
            return generate_vk_message(game)
        return game.description or game.title

    def render_ical(self, *, calendar_name: str, games: list[Game]) -> str:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:{self.settings.ical_product_id}",
            "CALSCALE:GREGORIAN",
            f"X-WR-CALNAME:{_escape_ical_text(calendar_name)}",
        ]
        for game in games:
            dtstamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dtstart = game.starts_at.astimezone(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dtend = (game.starts_at + timedelta(minutes=game.duration_minutes)).astimezone(
                timezone.utc
            ).strftime("%Y%m%dT%H%M%SZ")
            location = game.chat.title if game.chat and game.chat.title else "Game schedule bot"
            description = self._build_game_description(game)

            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:game-{game.id}@our_game_schedule_bot",
                    f"DTSTAMP:{dtstamp}",
                    f"DTSTART:{dtstart}",
                    f"DTEND:{dtend}",
                    f"SUMMARY:{_escape_ical_text(game.title)}",
                    f"DESCRIPTION:{_escape_ical_text(description)}",
                    f"LOCATION:{_escape_ical_text(location)}",
                    "END:VEVENT",
                ]
            )

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"
