from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import TimestampMixin


class Community(TimestampMixin, Base):
    """A logical group of chats that share games and participants."""

    __tablename__ = "communities"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chats = relationship("ChatSpace", back_populates="community")


class GamePublication(TimestampMixin, Base):
    __tablename__ = "game_publications"
    __table_args__ = (
        UniqueConstraint("chat_id", "message_id", name="uq_game_publications_chat_message"),
        UniqueConstraint("game_id", "chat_id", name="uq_game_publications_game_chat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chat_spaces.id", ondelete="CASCADE"), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    game = relationship("Game", back_populates="publications")
    chat = relationship("ChatSpace")
