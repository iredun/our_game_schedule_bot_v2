import enum

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import TimestampMixin


class Platform(enum.StrEnum):
    TELEGRAM = "telegram"
    VK = "vk"
    WEB = "web"


class PlatformAccount(TimestampMixin, Base):
    __tablename__ = "platform_accounts"
    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id", name="uq_platform_accounts_platform_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform, native_enum=False), nullable=False)
    platform_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user = relationship("UserProfile", back_populates="platform_accounts")
    authored_games = relationship("Game", back_populates="author_account")


class ChatSpace(TimestampMixin, Base):
    __tablename__ = "chat_spaces"
    __table_args__ = (
        UniqueConstraint("platform", "platform_chat_id", name="uq_chat_spaces_platform_chat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform, native_enum=False), nullable=False)
    platform_chat_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    games = relationship("Game", back_populates="chat")
    member_settings = relationship(
        "ChatMemberSettings",
        back_populates="chat",
        cascade="all, delete-orphan",
    )
