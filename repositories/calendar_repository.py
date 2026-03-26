from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import CalendarToken


class CalendarRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_active_token(self, user_id: int) -> CalendarToken | None:
        stmt = select(CalendarToken).where(
            CalendarToken.user_id == user_id,
            CalendarToken.is_active.is_(True),
        )
        return self.session.scalar(stmt)

    def get_by_token(self, token: str) -> CalendarToken | None:
        stmt = select(CalendarToken).where(
            CalendarToken.token == token,
            CalendarToken.is_active.is_(True),
        )
        return self.session.scalar(stmt)

    def touch(self, calendar_token: CalendarToken) -> None:
        calendar_token.last_used_at = datetime.now(timezone.utc)
        self.session.flush()
