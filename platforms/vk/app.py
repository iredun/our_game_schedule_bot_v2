import logging

from vkbottle.bot import Bot

from core.config import get_settings
from platforms.vk.handlers import register_handlers


settings = get_settings()


def build_application() -> Bot:
    bot = Bot(settings.vk_bot_token)
    register_handlers(bot)
    return bot


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    build_application().run_forever()


if __name__ == "__main__":
    main()
