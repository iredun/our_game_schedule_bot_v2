from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import TimestampMixin


class ChatMembership(TimestampMixin, Base):
    """Chats where a Telegram user has been observed interacting with the bot."""
    __tablename__ = "chat_memberships"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_memberships_chat_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chat_spaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    chat = relationship("ChatSpace")
    user = relationship("UserProfile")


class ChatMemberSettings(TimestampMixin, Base):
    __tablename__ = "chat_member_settings"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_member_settings_chat_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chat_spaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    custom_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    chat = relationship("ChatSpace", back_populates="member_settings")
    user = relationship("UserProfile")
