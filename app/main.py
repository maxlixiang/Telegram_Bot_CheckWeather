import logging

from dotenv import load_dotenv
from telegram.ext import Application

from app.bot.handlers import get_handlers, restore_daily_push_job
from app.config import load_settings, validate_settings
from app.db.database import init_storage


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main() -> None:
    load_dotenv()
    init_storage()

    settings = load_settings()
    validate_settings(settings)

    application = Application.builder().token(settings.telegram_bot_token).build()

    for handler in get_handlers():
        application.add_handler(handler)

    restore_daily_push_job(application)

    logging.info("Bot is starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
