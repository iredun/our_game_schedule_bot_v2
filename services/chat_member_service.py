from sqlalchemy.orm import Session

from db.models import ChatMemberSettings
from repositories.chat_member_repository import ChatMemberRepository


class ChatMemberService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ChatMemberRepository(session)

    def get_settings(self, *, chat_id: int, user_id: int) -> ChatMemberSettings | None:
        return self.repository.get(chat_id=chat_id, user_id=user_id)

    def set_custom_name(
        self,
        *,
        chat_id: int,
        user_id: int,
        custom_display_name: str,
    ) -> ChatMemberSettings:
        settings = self.repository.set_custom_name(
            chat_id=chat_id,
            user_id=user_id,
            custom_display_name=custom_display_name,
        )
        self.session.commit()
        return settings

    def clear_custom_name(self, *, chat_id: int, user_id: int) -> bool:
        deleted = self.repository.clear_custom_name(chat_id=chat_id, user_id=user_id)
        self.session.commit()
        return deleted
