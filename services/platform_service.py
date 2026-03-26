from sqlalchemy.orm import Session

from db.models import ChatSpace, Platform, PlatformAccount
from repositories.platform_repository import PlatformRepository


class PlatformService:
    def __init__(self, session: Session):
        self.repository = PlatformRepository(session)

    def register_account(
        self,
        *,
        platform: Platform,
        platform_user_id: str,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        display_name: str | None = None,
    ) -> PlatformAccount:
        return self.repository.get_or_create_user_by_platform_account(
            platform=platform,
            platform_user_id=platform_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
        )

    def register_chat(
        self,
        *,
        platform: Platform,
        platform_chat_id: str,
        title: str | None = None,
    ) -> ChatSpace:
        return self.repository.get_or_create_chat(
            platform=platform,
            platform_chat_id=platform_chat_id,
            title=title,
        )
