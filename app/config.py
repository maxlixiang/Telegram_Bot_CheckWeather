from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    telegram_user_id: str
    weather_api_key: str
    default_timezone: str


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_user_id=os.getenv("TELEGRAM_USER_ID", "").strip(),
        weather_api_key=os.getenv("WEATHER_API_KEY", "").strip(),
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "UTC").strip(),
    )


def validate_settings(settings: Settings) -> None:
    if not settings.telegram_bot_token:
        raise ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")
