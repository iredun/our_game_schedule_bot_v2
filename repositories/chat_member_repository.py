from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ChatMemberSettings, ChatMembership


class ChatMemberRepository:
    def __init__(self, session: Session):
        self.session = session

    def observe_membership(self, *, chat_id: int, user_id: int) -> ChatMembership:
        stmt = select(ChatMembership).where(
            ChatMembership.chat_id == chat_id, ChatMembership.user_id == user_id
        )
        membership = self.session.scalar(stmt)
        if membership is None:
            membership = ChatMembership(chat_id=chat_id, user_id=user_id)
            self.session.add(membership)
            self.session.flush()
        return membership

    def list_memberships(self, *, user_id: int) -> list[ChatMembership]:
        stmt = select(ChatMembership).where(ChatMembership.user_id == user_id)
        return list(self.session.scalars(stmt))

    def get(self, *, chat_id: int, user_id: int) -> ChatMemberSettings | None:
        stmt = select(ChatMemberSettings).where(
            ChatMemberSettings.chat_id == chat_id,
            ChatMemberSettings.user_id == user_id,
        )
        return self.session.scalar(stmt)

    def set_custom_name(
        self,
        *,
        chat_id: int,
        user_id: int,
        custom_display_name: str,
    ) -> ChatMemberSettings:
        member_settings = self.get(chat_id=chat_id, user_id=user_id)
        if member_settings is None:
            member_settings = ChatMemberSettings(
                chat_id=chat_id,
                user_id=user_id,
                custom_display_name=custom_display_name,
            )
            self.session.add(member_settings)
        else:
            member_settings.custom_display_name = custom_display_name

        self.session.flush()
        return member_settings

    def clear_custom_name(self, *, chat_id: int, user_id: int) -> bool:
        member_settings = self.get(chat_id=chat_id, user_id=user_id)
        if member_settings is None:
            return False

        self.session.delete(member_settings)
        self.session.flush()
        return True
