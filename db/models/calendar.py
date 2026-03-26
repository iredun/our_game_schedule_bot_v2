import secrets
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import TimestampMixin


class CalendarToken(TimestampMixin, Base):
    __tablename__ = "calendar_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        default=lambda: secrets.token_urlsafe(32),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("UserProfile", back_populates="calendar_tokens")
