from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    telegram_user_id: str
    weather_api_key: str
    deepseek_api_key: str
    deepseek_model: str
    default_timezone: str


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_user_id=os.getenv("TELEGRAM_USER_ID", "").strip(),
        weather_api_key=os.getenv("WEATHER_API_KEY", "").strip(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat",
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "UTC").strip(),
    )


def validate_settings(settings: Settings) -> None:
    if not settings.telegram_bot_token:
        raise ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")
    if not settings.telegram_user_id:
        raise ValueError("Missing required environment variable: TELEGRAM_USER_ID")
    if not settings.deepseek_api_key:
        raise ValueError("Missing required environment variable: DEEPSEEK_API_KEY")
