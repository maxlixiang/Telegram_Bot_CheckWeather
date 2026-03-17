from datetime import datetime, time
import logging
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import Update
from telegram.ext import Application, BaseHandler, CommandHandler, ContextTypes

from app.config import load_settings
from app.db.database import (
    DEFAULT_PUSH_HOUR,
    DEFAULT_PUSH_MINUTE,
    StoredCity,
    add_city_record,
    delete_city,
    find_city_by_normalized_key,
    get_push_time,
    is_push_enabled,
    list_cities,
    set_push_enabled,
    set_push_time,
    update_city_metadata,
)
from app.services.weather_service import (
    CityNotFoundError,
    CityWeatherResult,
    WeatherService,
    WeatherServiceError,
)


logger = logging.getLogger(__name__)

UNAUTHORIZED_TEXT = "无权限使用该命令。"
EMPTY_CITIES_TEXT = "当前没有已保存城市，请先使用 /add 添加城市。"
SETTIME_USAGE_TEXT = "用法：/settime HH:MM，例如 /settime 08:30"
PUSH_ENABLED_TEXT = "已开启每日自动天气推送。"
PUSH_DISABLED_TEXT = "已关闭每日自动天气推送。"
PUSH_ALREADY_ENABLED_TEXT = "自动天气推送已开启。"
PUSH_ALREADY_DISABLED_TEXT = "自动天气推送已关闭。"
DAILY_PUSH_JOB_NAME = "daily_weather_push"
DEFAULT_FALLBACK_TIMEZONE = "UTC"
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

HELP_TEXT = f"""
Telegram Weather Bot

当前已支持：
- /help
- /check
- /add 城市名
- /delete 城市名
- /list
- /start = 开启每日自动天气推送
- /stop = 关闭每日自动天气推送
- /settime HH:MM = 设置每日自动推送时间，例如 /settime 08:30

默认推送时间为 {DEFAULT_PUSH_HOUR:02d}:{DEFAULT_PUSH_MINUTE:02d}，可以通过 /settime HH:MM 修改。
当前机器人仅服务单用户，只有配置的 TELEGRAM_USER_ID 可以使用 /check、/add、/delete、/list、/start、/stop、/settime。
""".strip()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT)


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    try:
        message = build_weather_text()
    except WeatherServiceError:
        await reply_text(update, "天气服务暂时不可用，请稍后再试。")
        return

    if not message:
        await reply_text(update, EMPTY_CITIES_TEXT)
        return

    await reply_text(update, message)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    city_name = normalize_city_name(" ".join(context.args))
    if not city_name:
        await reply_text(update, "用法：/add 城市名")
        return

    settings = load_settings()
    service = WeatherService()

    try:
        resolved = service.resolve_city(city_name)
    except CityNotFoundError:
        await reply_text(update, f"未找到城市：{city_name}，请尝试更具体的名称。")
        return
    except WeatherServiceError:
        await reply_text(update, "城市查询服务暂时不可用，请稍后再试。")
        return

    existing = find_city_by_normalized_key(settings.telegram_user_id, resolved.normalized_key)
    if existing:
        await reply_text(update, f"城市已存在：{existing.display_name or existing.city_name}")
        return

    add_city_record(
        user_id=settings.telegram_user_id,
        city_name=city_name,
        display_name=resolved.display_name,
        latitude=resolved.latitude,
        longitude=resolved.longitude,
        normalized_key=resolved.normalized_key,
    )
    await reply_text(update, f"已添加城市：{resolved.display_name}")


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
    lines.extend(f"- {city.display_name or city.city_name}" for city in cities)
    await reply_text(update, "\n".join(lines))


async def start_push_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    settings = load_settings()
    already_enabled = is_push_enabled(settings.telegram_user_id)
    set_push_enabled(settings.telegram_user_id, True)
    schedule_daily_push(context.application)

    if already_enabled:
        await reply_text(update, PUSH_ALREADY_ENABLED_TEXT)
        return

    await reply_text(update, PUSH_ENABLED_TEXT)


async def stop_push_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    settings = load_settings()
    if not is_push_enabled(settings.telegram_user_id):
        await reply_text(update, PUSH_ALREADY_DISABLED_TEXT)
        return

    set_push_enabled(settings.telegram_user_id, False)
    remove_daily_push_job(context.application)
    await reply_text(update, PUSH_DISABLED_TEXT)


async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_authorized(update):
        return

    if len(context.args) != 1:
        await reply_text(update, SETTIME_USAGE_TEXT)
        return

    parsed = parse_push_time(context.args[0])
    if not parsed:
        await reply_text(update, SETTIME_USAGE_TEXT)
        return

    hour, minute = parsed
    settings = load_settings()
    set_push_time(settings.telegram_user_id, hour, minute)

    if is_push_enabled(settings.telegram_user_id):
        schedule_daily_push(context.application)

    await reply_text(update, f"已将每日自动推送时间设置为 {hour:02d}:{minute:02d}")


async def daily_push_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_settings()

    try:
        message = build_weather_text()
    except WeatherServiceError:
        logger.warning("Daily weather push failed because weather service is unavailable.")
        return

    if not message:
        logger.info("Daily weather push skipped because no cities are saved.")
        return

    await context.bot.send_message(chat_id=int(settings.telegram_user_id), text=message)


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


def parse_push_time(value: str) -> tuple[int, int] | None:
    match = TIME_PATTERN.fullmatch(value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def build_weather_text() -> str | None:
    settings = load_settings()
    cities = list_cities(settings.telegram_user_id)
    if not cities:
        return None

    service = WeatherService()
    reports: list[CityWeatherResult] = []

    for city in cities:
        try:
            weather_target = prepare_weather_city(service, city)
            reports.append(
                service.get_weather_for_location(
                    city_label=weather_target.display_name or weather_target.city_name,
                    latitude=weather_target.latitude,
                    longitude=weather_target.longitude,
                    timezone=settings.default_timezone,
                )
            )
        except CityNotFoundError:
            reports.append(
                CityWeatherResult(
                    city=city.display_name or city.city_name,
                    error="未找到城市位置信息。",
                )
            )
        except WeatherServiceError as exc:
            reports.append(
                CityWeatherResult(
                    city=city.display_name or city.city_name,
                    error=str(exc),
                )
            )

    if reports and all(report.error for report in reports):
        raise WeatherServiceError("天气服务暂时不可用，请稍后再试。")

    return format_check_message(reports)


def prepare_weather_city(service: WeatherService, city: StoredCity) -> StoredCity:
    if city.latitude is not None and city.longitude is not None:
        return city

    resolved = service.resolve_city(city.city_name)
    update_city_metadata(
        city_id=city.id,
        display_name=resolved.display_name,
        latitude=resolved.latitude,
        longitude=resolved.longitude,
        normalized_key=resolved.normalized_key,
    )
    city.display_name = resolved.display_name
    city.latitude = resolved.latitude
    city.longitude = resolved.longitude
    city.normalized_key = resolved.normalized_key
    return city


def format_check_message(city_reports: list[CityWeatherResult]) -> str:
    sections = ["🌦️ 天气简报"]

    for report in city_reports:
        sections.append(format_city_weather(report))

    return "\n\n".join(sections)


def format_city_weather(report: CityWeatherResult) -> str:
    if report.error:
        return f"📍 {report.city}\n⚠️ 查询失败：{report.error}"

    current = report.current or {}
    daily = report.daily or []

    lines = [
        f"📍 {report.city}",
        (
            f"{current.get('weather_emoji', '❓')} 当前：{current.get('weather', '未知')}  "
            f"{format_temperature(current.get('temperature'))}"
            f"（体感 {format_temperature(current.get('apparent_temperature'))}）"
        ),
        f"💨 风速：{format_wind_speed(current.get('wind_speed'))}",
        "📅 未来 7 天",
    ]

    for item in daily:
        lines.append(
            f"• {format_date(item.get('date'))} "
            f"{item.get('weather_emoji', '❓')} {item.get('weather', '未知')}  "
            f"{format_temp_range(item.get('temp_min'), item.get('temp_max'))}  "
            f"☔ {format_percentage(item.get('precipitation_probability'))}"
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


def format_temp_range(temp_min: float | int | None, temp_max: float | int | None) -> str:
    return f"{format_temperature(temp_min)} ~ {format_temperature(temp_max)}"


def format_wind_speed(value: float | int | None) -> str:
    if value is None:
        return "--"
    return f"{round(value)} km/h"


def format_percentage(value: float | int | None) -> str:
    if value is None:
        return "--"
    return f"{round(value)}%"


def get_scheduled_push_time() -> time:
    settings = load_settings()
    hour, minute = get_push_time(settings.telegram_user_id)

    try:
        timezone = ZoneInfo(settings.default_timezone)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Invalid timezone '%s'. Falling back to %s.",
            settings.default_timezone,
            DEFAULT_FALLBACK_TIMEZONE,
        )
        timezone = ZoneInfo(DEFAULT_FALLBACK_TIMEZONE)

    return time(hour=hour, minute=minute, tzinfo=timezone)


def schedule_daily_push(application: Application) -> None:
    job_queue = application.job_queue
    if job_queue is None:
        logger.warning("JobQueue is not available. Daily push will not be scheduled.")
        return

    settings = load_settings()
    remove_daily_push_job(application)

    job_queue.run_daily(
        daily_push_callback,
        time=get_scheduled_push_time(),
        name=DAILY_PUSH_JOB_NAME,
        chat_id=int(settings.telegram_user_id),
        user_id=int(settings.telegram_user_id),
    )


def remove_daily_push_job(application: Application) -> None:
    job_queue = application.job_queue
    if job_queue is None:
        return

    for job in job_queue.get_jobs_by_name(DAILY_PUSH_JOB_NAME):
        job.schedule_removal()


def restore_daily_push_job(application: Application) -> None:
    settings = load_settings()
    if not settings.telegram_user_id:
        logger.warning("TELEGRAM_USER_ID is not set. Skip restoring daily push job.")
        return

    if is_push_enabled(settings.telegram_user_id):
        schedule_daily_push(application)
        logger.info("Restored daily weather push job.")


def get_handlers() -> list[BaseHandler]:
    return [
        CommandHandler("help", help_command),
        CommandHandler("check", check_command),
        CommandHandler("add", add_command),
        CommandHandler("delete", delete_command),
        CommandHandler("list", list_command),
        CommandHandler("start", start_push_command),
        CommandHandler("stop", stop_push_command),
        CommandHandler("settime", settime_command),
    ]
