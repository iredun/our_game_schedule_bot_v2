import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import TimestampMixin


class GameStatus(enum.StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class GameParticipantStatus(enum.StrEnum):
    GOING = "going"
    MAYBE = "maybe"
    PLUS_ONE = "plus_one"


class Game(TimestampMixin, Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chat_spaces.id", ondelete="CASCADE"), nullable=False)
    author_account_id: Mapped[int] = mapped_column(
        ForeignKey("platform_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    price_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=2500)
    max_players_count: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus, native_enum=False),
        default=GameStatus.ACTIVE,
        nullable=False,
    )
    source_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    chat = relationship("ChatSpace", back_populates="games")
    author_account = relationship("PlatformAccount", back_populates="authored_games")
    participants = relationship("GameParticipant", back_populates="game", cascade="all, delete-orphan")


class GameParticipant(TimestampMixin, Base):
    __tablename__ = "game_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[GameParticipantStatus] = mapped_column(
        Enum(GameParticipantStatus, native_enum=False),
        nullable=False,
    )
    display_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)

    game = relationship("Game", back_populates="participants")
    user = relationship("UserProfile", back_populates="game_participations")
