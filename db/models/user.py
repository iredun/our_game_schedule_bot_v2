from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import TimestampMixin


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)

    platform_accounts = relationship("PlatformAccount", back_populates="user", cascade="all, delete-orphan")
    game_participations = relationship("GameParticipant", back_populates="user", cascade="all, delete-orphan")
    calendar_tokens = relationship("CalendarToken", back_populates="user", cascade="all, delete-orphan")
