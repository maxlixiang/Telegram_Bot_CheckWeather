from datetime import datetime
import re

from telegram import Update
from telegram.ext import BaseHandler, CommandHandler, ContextTypes

from app.config import load_settings
from app.db.database import add_city, delete_city, list_cities
from app.services.weather_service import CityWeatherResult, WeatherService, WeatherServiceError


UNAUTHORIZED_TEXT = "无权限使用该命令。"
EMPTY_CITIES_TEXT = "当前没有已保存城市，请先使用 /add 添加城市。"

HELP_TEXT = """
Telegram Weather Bot

当前已支持：
- /help
- /check
- /add 城市名
- /delete 城市名
- /list

未实现：
- /start
- /stop

当前机器人仅服务单用户，只有配置的 TELEGRAM_USER_ID 可以使用 /check、/add、/delete、/list。
""".strip()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT)


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    settings = load_settings()
    cities = list_cities(settings.telegram_user_id)
    if not cities:
        await reply_text(update, EMPTY_CITIES_TEXT)
        return

    service = WeatherService()

    try:
        city_reports = service.get_cities_weather(cities=cities, timezone=settings.default_timezone)
    except WeatherServiceError:
        await reply_text(update, "天气服务暂时不可用，请稍后再试。")
        return

    await reply_text(update, format_check_message(city_reports))


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    city_name = normalize_city_name(" ".join(context.args))
    if not city_name:
        await reply_text(update, "用法：/add 城市名")
        return

    settings = load_settings()
    if add_city(settings.telegram_user_id, city_name):
        await reply_text(update, f"已添加城市：{city_name}")
        return

    await reply_text(update, f"城市已存在：{city_name}")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    city_name = normalize_city_name(" ".join(context.args))
    if not city_name:
        await reply_text(update, "用法：/delete 城市名")
        return

    settings = load_settings()
    if delete_city(settings.telegram_user_id, city_name):
        await reply_text(update, f"已删除城市：{city_name}")
        return

    await reply_text(update, f"城市不存在：{city_name}")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    settings = load_settings()
    cities = list_cities(settings.telegram_user_id)
    if not cities:
        await reply_text(update, EMPTY_CITIES_TEXT)
        return

    lines = ["当前城市列表："]
    lines.extend(f"- {city}" for city in cities)
    await reply_text(update, "\n".join(lines))


async def ensure_authorized(update: Update) -> bool:
    settings = load_settings()
    user = update.effective_user

    if user and settings.telegram_user_id and str(user.id) == settings.telegram_user_id:
        return True

    await reply_text(update, UNAUTHORIZED_TEXT)
    return False


async def reply_text(update: Update, text: str) -> None:
    if update.message:
        await update.message.reply_text(text)


def normalize_city_name(city_name: str) -> str:
    return re.sub(r"\s+", " ", city_name).strip()


def format_check_message(city_reports: list[CityWeatherResult]) -> str:
    sections = ["当前城市天气"]

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
        CommandHandler("add", add_command),
        CommandHandler("delete", delete_command),
        CommandHandler("list", list_command),
    ]
