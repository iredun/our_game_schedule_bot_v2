from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.config import get_settings
from db.models import Game, GameParticipantStatus
from repositories.game_repository import GameRepository


class GameService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = GameRepository(session)
        self.settings = get_settings()

    def create_game(
        self,
        *,
        chat_id: int,
        author_account_id: int,
        title: str,
        starts_at: datetime,
        description: str | None = None,
        duration_minutes: int | None = None,
        price_per_hour: int | None = None,
        max_players_count: int | None = None,
        source_message_id: str | None = None,
    ) -> Game:
        game = Game(
            chat_id=chat_id,
            author_account_id=author_account_id,
            title=title,
            description=description,
            starts_at=starts_at,
            duration_minutes=(duration_minutes if duration_minutes is not None else self.settings.default_game_duration_minutes),
            price_per_hour=(price_per_hour if price_per_hour is not None else self.settings.default_game_price),
            max_players_count=(max_players_count if max_players_count is not None else self.settings.default_max_players_count),
            source_message_id=source_message_id,
        )
        self.repository.create_game(game)
        self.session.commit()
        return game

    def set_participation(
        self,
        *,
        game_id: int,
        user_id: int,
        status: GameParticipantStatus,
        display_name_snapshot: str | None = None,
    ):
        participation = self.repository.set_participation(
            game_id=game_id,
            user_id=user_id,
            status=status,
            display_name_snapshot=display_name_snapshot,
        )
        self.session.commit()
        return participation

    def add_participation(
        self,
        *,
        game_id: int,
        user_id: int,
        status: GameParticipantStatus,
        display_name_snapshot: str | None = None,
    ):
        participation = self.repository.add_participation(
            game_id=game_id,
            user_id=user_id,
            status=status,
            display_name_snapshot=display_name_snapshot,
        )
        self.session.commit()
        return participation

    def remove_participation(
        self,
        *,
        game_id: int,
        user_id: int,
        status: GameParticipantStatus,
    ) -> bool:
        deleted = self.repository.delete_participation(
            game_id=game_id,
            user_id=user_id,
            status=status,
        )
        self.session.commit()
        return deleted

    def set_main_status(
        self,
        *,
        game_id: int,
        user_id: int,
        status: GameParticipantStatus,
        display_name_snapshot: str | None = None,
    ) -> bool:
        current_statuses = [
            GameParticipantStatus.GOING,
            GameParticipantStatus.MAYBE,
        ]
        existing = [
            self.repository.get_participation(game_id=game_id, user_id=user_id, status=item_status)
            for item_status in current_statuses
        ]
        existing = [item for item in existing if item is not None]

        if status == GameParticipantStatus.GOING and any(
            item.status == GameParticipantStatus.GOING for item in existing
        ):
            return False

        if existing:
            primary_participation = existing[0]
            primary_participation.status = status
            primary_participation.display_name_snapshot = display_name_snapshot
            for extra_participation in existing[1:]:
                self.session.delete(extra_participation)
            self.session.commit()
            return True

        self.repository.set_participation(
            game_id=game_id,
            user_id=user_id,
            status=status,
            display_name_snapshot=display_name_snapshot,
        )
        self.session.commit()
        return True

    def remove_main_status(self, *, game_id: int, user_id: int) -> bool:
        deleted = self.repository.delete_main_participations(game_id=game_id, user_id=user_id)
        self.session.commit()
        return deleted

    def get_game_by_source_message(self, *, chat_id: int, source_message_id: str) -> Game | None:
        return self.repository.get_game_by_source_message(
            chat_id=chat_id,
            source_message_id=source_message_id,
        )

    def get_game(self, *, game_id: int) -> Game | None:
        return self.repository.get_game(game_id)

    def list_chat_games(self, *, chat_id: int) -> list[Game]:
        return self.repository.list_active_games_for_chat(chat_id=chat_id)

    def list_current_chat_games(self, *, chat_id: int, from_dt: datetime) -> list[Game]:
        earliest_start = from_dt - timedelta(minutes=720)
        games = self.repository.list_games_started_after(chat_id=chat_id, from_dt=earliest_start)
        current_games = []
        for game in games:
            starts_at = game.starts_at
            if starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=self.settings.timezone)
            if starts_at + timedelta(minutes=game.duration_minutes) > from_dt:
                current_games.append(game)
        return current_games

    def cleanup_old_chat_games(self, *, chat_id: int, before_dt: datetime) -> int:
        deleted = self.repository.delete_games_before(chat_id=chat_id, before_dt=before_dt)
        self.session.commit()
        return deleted

    def update_game_settings(
        self,
        game: Game,
        *,
        starts_at: datetime | None = None,
        price_per_hour: int | None = None,
        duration_minutes: int | None = None,
        max_players_count: int | None = None,
        description: str | None = None,
        title: str | None = None,
        commit: bool = True,
    ) -> Game:
        fields: dict[str, object] = {}
        if starts_at is not None:
            fields["starts_at"] = starts_at
        if price_per_hour is not None:
            fields["price_per_hour"] = price_per_hour
        if duration_minutes is not None:
            fields["duration_minutes"] = duration_minutes
        if max_players_count is not None:
            fields["max_players_count"] = max_players_count
        if description is not None:
            fields["description"] = description
        if title is not None:
            fields["title"] = title

        updated_game = self.repository.update_game_fields(game, **fields)
        if commit:
            self.session.commit()
        return updated_game

    def delete_game(self, game: Game) -> None:
        self.repository.delete_game(game)
        self.session.commit()

    def get_user_games(self, *, user_id: int, from_dt: datetime | None = None) -> list[Game]:
        return self.repository.get_active_games_for_user(user_id=user_id, from_dt=from_dt)
