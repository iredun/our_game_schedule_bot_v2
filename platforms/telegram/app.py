import logging

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from core.config import get_settings
from platforms.telegram.handlers import (
    buttons,
    calendar_link,
    delete_schedule,
    list_schedule,
    mynameis,
    new_schedule,
    set_max_players_count,
    set_price,
    set_time,
    start,
)


settings = get_settings()


def build_application():
    application = ApplicationBuilder().token(settings.telegram_bot_token).build()
    application.add_handler(CallbackQueryHandler(buttons))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("calendar_link", calendar_link))
    application.add_handler(CommandHandler("new", new_schedule))
    application.add_handler(CommandHandler("delete", delete_schedule))
    application.add_handler(CommandHandler("list", list_schedule))
    application.add_handler(CommandHandler("mynameis", mynameis))
    application.add_handler(CommandHandler("price", set_price))
    application.add_handler(CommandHandler("set_time", set_time))
    application.add_handler(CommandHandler("max_players_count", set_max_players_count))
    return application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    build_application().run_polling()


if __name__ == "__main__":
    main()
