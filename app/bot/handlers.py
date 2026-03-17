from datetime import datetime

from telegram import Update
from telegram.ext import BaseHandler, CommandHandler, ContextTypes

from app.config import load_settings
from app.services.weather_service import CityWeatherResult, WeatherService, WeatherServiceError


HELP_TEXT = """
Telegram Weather Bot

Current phase:
- /help command is available
- /check supports fixed cities: 北京、上海

Planned commands:
- /add
- /delete
- /list
- /start
- /stop

Real city management and auto push are not implemented yet.
""".strip()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT)


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    settings = load_settings()
    service = WeatherService()

    try:
        city_reports = service.get_fixed_cities_weather(timezone=settings.default_timezone)
    except WeatherServiceError:
        await update.message.reply_text("天气服务暂时不可用，请稍后再试。")
        return

    await update.message.reply_text(format_check_message(city_reports))


def format_check_message(city_reports: list[CityWeatherResult]) -> str:
    sections = ["固定城市天气"]

    for report in city_reports:
        sections.append(format_city_weather(report))

    return "\n\n".join(sections)


def format_city_weather(report: CityWeatherResult) -> str:
    if report.error:
        return f"{report.city}\n查询失败：{report.error}"

    current = report.current or {}
    daily = report.daily or []

    lines = [
        report.city,
        (
            "当前天气："
            f"{current.get('weather', '未知')}，"
            f"{format_temperature(current.get('temperature'))}，"
            f"体感 {format_temperature(current.get('apparent_temperature'))}，"
            f"风速 {format_wind_speed(current.get('wind_speed'))}"
        ),
        "未来 7 天：",
    ]

    for item in daily:
        lines.append(
            f"{format_date(item.get('date'))} "
            f"{item.get('weather', '未知')} "
            f"{format_temperature(item.get('temp_min'))}~{format_temperature(item.get('temp_max'))} "
            f"降水概率 {format_percentage(item.get('precipitation_probability'))}"
        )

    return "\n".join(lines)


def format_date(value: str | None) -> str:
    if not value:
        return "--.--"
    return datetime.strptime(value, "%Y-%m-%d").strftime("%m-%d")


def format_temperature(value: float | int | None) -> str:
    if value is None:
        return "--"
    return f"{round(value)}°C"


def format_wind_speed(value: float | int | None) -> str:
    if value is None:
        return "--"
    return f"{round(value)} km/h"


def format_percentage(value: float | int | None) -> str:
    if value is None:
        return "--"
    return f"{round(value)}%"


def get_handlers() -> list[BaseHandler]:
    return [
        CommandHandler("help", help_command),
        CommandHandler("check", check_command),
    ]
