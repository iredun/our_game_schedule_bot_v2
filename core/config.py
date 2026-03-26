from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytz import timezone
from datetime import tzinfo


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "our_game_schedule_bot"
    app_base_url: str = "http://localhost:8000"
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    vk_bot_token: str = Field(default="", alias="VK_BOT_TOKEN")
    telegram_allowed_chat_ids_raw: str = Field(default="", alias="TELEGRAM_ALLOWED_CHAT_IDS")
    vk_allowed_chat_ids_raw: str = Field(default="", alias="VK_ALLOWED_CHAT_IDS")
    database_url: str = Field(
        default=f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}",
        alias="DATABASE_URL",
    )
    timezone_raw: str = Field(default="Europe/Moscow", alias="TIMEZONE")
    default_game_price: int = 2000
    default_game_duration_minutes: int = 120
    default_max_players_count: int = 14
    ical_product_id: str = "-//our_game_schedule_bot//EN"

    @property
    def telegram_allowed_chat_ids(self) -> set[int]:
        if not self.telegram_allowed_chat_ids_raw.strip():
            return set()
        return {
            int(chat_id.strip())
            for chat_id in self.telegram_allowed_chat_ids_raw.split(",")
            if chat_id.strip()
        }

    @property
    def timezone(self) -> tzinfo:
        return timezone(self.timezone_raw)

    @property
    def vk_allowed_chat_ids(self) -> set[int]:
        if not self.vk_allowed_chat_ids_raw.strip():
            return set()
        return {
            int(chat_id.strip())
            for chat_id in self.vk_allowed_chat_ids_raw.split(",")
            if chat_id.strip()
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
