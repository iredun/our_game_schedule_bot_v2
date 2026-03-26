from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ChatSpace, Platform, PlatformAccount, UserProfile


class PlatformRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_user_by_platform_account(
        self,
        *,
        platform: Platform,
        platform_user_id: str,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        display_name: str | None = None,
    ) -> PlatformAccount:
        stmt = select(PlatformAccount).where(
            PlatformAccount.platform == platform,
            PlatformAccount.platform_user_id == platform_user_id,
        )
        account = self.session.scalar(stmt)
        if account:
            account.username = username
            account.first_name = first_name
            account.last_name = last_name
            if display_name:
                account.user.display_name = display_name
            return account

        user = UserProfile(display_name=display_name)
        account = PlatformAccount(
            user=user,
            platform=platform,
            platform_user_id=platform_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        self.session.add(account)
        self.session.flush()
        return account

    def get_or_create_chat(
        self,
        *,
        platform: Platform,
        platform_chat_id: str,
        title: str | None = None,
    ) -> ChatSpace:
        stmt = select(ChatSpace).where(
            ChatSpace.platform == platform,
            ChatSpace.platform_chat_id == platform_chat_id,
        )
        chat = self.session.scalar(stmt)
        if chat:
            chat.title = chat.title or title
            return chat

        chat = ChatSpace(
            platform=platform,
            platform_chat_id=platform_chat_id,
            title=title,
        )
        self.session.add(chat)
        self.session.flush()
        return chat
