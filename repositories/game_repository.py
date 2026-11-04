from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from db.models import Game, GameParticipant, GameParticipantStatus, GameStatus


class GameRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_game(self, game: Game) -> Game:
        self.session.add(game)
        self.session.flush()
        return game

    def get_game(self, game_id: int) -> Game | None:
        stmt = (
            select(Game)
            .options(
                joinedload(Game.participants).joinedload(GameParticipant.user),
                joinedload(Game.chat),
                joinedload(Game.author_account),
            )
            .where(Game.id == game_id)
        )
        return self.session.scalar(stmt)

    def get_game_by_source_message(self, *, chat_id: int, source_message_id: str) -> Game | None:
        stmt = (
            select(Game)
            .options(
                joinedload(Game.participants).joinedload(GameParticipant.user),
                joinedload(Game.chat),
                joinedload(Game.author_account),
            )
            .where(
                Game.chat_id == chat_id,
                Game.source_message_id == source_message_id,
                Game.status == GameStatus.ACTIVE,
            )
        )
        return self.session.scalar(stmt)

    def list_active_games_for_chat(self, *, chat_id: int) -> list[Game]:
        stmt = (
            select(Game)
            .where(Game.chat_id == chat_id, Game.status == GameStatus.ACTIVE)
            .order_by(Game.starts_at.asc())
        )
        return list(self.session.scalars(stmt))

    def list_games_started_after(self, *, chat_id: int, from_dt: datetime) -> list[Game]:
        stmt = (
            select(Game)
            .where(
                Game.chat_id == chat_id,
                Game.status == GameStatus.ACTIVE,
                Game.starts_at >= from_dt,
            )
            .order_by(Game.starts_at.asc())
        )
        return list(self.session.scalars(stmt))

    def get_active_games_for_user(self, user_id: int, from_dt: datetime | None = None) -> list[Game]:
        stmt = (
            select(Game)
            .join(GameParticipant, GameParticipant.game_id == Game.id)
            .options(joinedload(Game.chat))
            .where(
                GameParticipant.user_id == user_id,
                GameParticipant.status.in_(
                    [GameParticipantStatus.GOING, GameParticipantStatus.MAYBE]
                ),
                Game.status == GameStatus.ACTIVE,
            )
            .order_by(Game.starts_at.asc())
        )
        if from_dt is not None:
            stmt = stmt.where(Game.starts_at >= from_dt)
        return list(self.session.scalars(stmt).unique())

    def get_participation(
        self,
        *,
        game_id: int,
        user_id: int,
        status: GameParticipantStatus,
    ) -> GameParticipant | None:
        stmt = select(GameParticipant).where(
            GameParticipant.game_id == game_id,
            GameParticipant.user_id == user_id,
            GameParticipant.status == status,
        )
        return self.session.scalar(stmt)

    def set_participation(
        self,
        *,
        game_id: int,
        user_id: int,
        status: GameParticipantStatus,
        display_name_snapshot: str | None = None,
    ) -> GameParticipant:
        participation = self.get_participation(game_id=game_id, user_id=user_id, status=status)
        if participation is None:
            participation = GameParticipant(
                game_id=game_id,
                user_id=user_id,
                status=status,
                display_name_snapshot=display_name_snapshot,
            )
            self.session.add(participation)
        else:
            participation.display_name_snapshot = display_name_snapshot

        self.session.flush()
        return participation

    def add_participation(
        self,
        *,
        game_id: int,
        user_id: int,
        status: GameParticipantStatus,
        display_name_snapshot: str | None = None,
    ) -> GameParticipant:
        participation = GameParticipant(
            game_id=game_id,
            user_id=user_id,
            status=status,
            display_name_snapshot=display_name_snapshot,
        )
        self.session.add(participation)
        self.session.flush()
        return participation

    def delete_participation(
        self,
        *,
        game_id: int,
        user_id: int,
        status: GameParticipantStatus,
    ) -> bool:
        participation = self.get_participation(game_id=game_id, user_id=user_id, status=status)
        if participation is None:
            return False

        self.session.delete(participation)
        self.session.flush()
        return True

    def delete_main_participations(self, *, game_id: int, user_id: int) -> bool:
        stmt = select(GameParticipant).where(
            GameParticipant.game_id == game_id,
            GameParticipant.user_id == user_id,
            GameParticipant.status.in_(
                [GameParticipantStatus.GOING, GameParticipantStatus.MAYBE]
            ),
        )
        participations = list(self.session.scalars(stmt))
        if not participations:
            return False
        for participation in participations:
            self.session.delete(participation)
        self.session.flush()
        return True

    def update_game_fields(self, game: Game, **fields: object) -> Game:
        for key, value in fields.items():
            setattr(game, key, value)
        self.session.flush()
        return game

    def delete_game(self, game: Game) -> None:
        self.session.delete(game)
        self.session.flush()

    def delete_games_before(self, *, chat_id: int, before_dt: datetime) -> int:
        stmt = delete(Game).where(
            Game.chat_id == chat_id,
            Game.starts_at < before_dt,
            Game.status == GameStatus.ACTIVE,
        )
        result = self.session.execute(stmt)
        self.session.flush()
        return result.rowcount or 0
