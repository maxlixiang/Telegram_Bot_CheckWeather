from dataclasses import dataclass
from datetime import datetime
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import load_settings


logger = logging.getLogger(__name__)

NORMALIZED_COORD_PRECISION = 4
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
REQUEST_TIMEOUT_SECONDS = 20
QUERY_FORECAST_DAYS = 7
EXPECTED_DAILY_FIELDS = {"date", "weather", "temp_min", "temp_max", "precipitation_probability"}
EXPECTED_CURRENT_FIELDS = {"weather", "temperature", "apparent_temperature", "wind_speed"}
WEATHER_TEXT_ALIASES = [
    (("雷暴", "雷阵雨"), ("雷暴", "⛈️")),
    (("暴雨",), ("暴雨", "🌧️")),
    (("大雨",), ("大雨", "🌧️")),
    (("中雨",), ("中雨", "🌧️")),
    (("小雨",), ("小雨", "🌧️")),
    (("阵雨", "雷阵雨"), ("阵雨", "🌦️")),
    (("冻雨",), ("冻雨", "🌧️")),
    (("雨夹雪",), ("雨夹雪", "🌨️")),
    (("小雪",), ("小雪", "🌨️")),
    (("中雪",), ("中雪", "🌨️")),
    (("大雪",), ("大雪", "❄️")),
    (("阵雪",), ("阵雪", "🌨️")),
    (("雾", "霾", "烟霾", "薄雾"), ("雾", "🌫️")),
    (("阴",), ("阴", "☁️")),
    (("多云",), ("多云", "⛅")),
    (("晴间多云", "少云", "晴时多云"), ("晴间多云", "🌤️")),
    (("晴",), ("晴", "☀️")),
]


class WeatherServiceError(Exception):
    """Raised when weather data cannot be fetched."""


class CityNotFoundError(WeatherServiceError):
    """Raised when a city cannot be resolved."""


@dataclass(slots=True)
class ResolvedCity:
    query_name: str
    display_name: str
    latitude: float
    longitude: float
    normalized_key: str


@dataclass(slots=True)
class CityWeatherResult:
    city: str
    current: dict | None = None
    daily: list[dict] | None = None
    error: str | None = None


class WeatherService:
    """Fetch current weather and 7-day forecast from DeepSeek."""

    def __init__(self) -> None:
        settings = load_settings()
        self.api_key = settings.deepseek_api_key
        self.model = settings.deepseek_model

    def resolve_city(self, city: str) -> ResolvedCity:
        payload = self._request_model_json(
            user_prompt=(
                "请识别用户输入的城市，并返回稳定的地点信息。"
                "如果无法确定地点，请返回 {\"found\": false, \"reason\": \"...\"}。"
                "如果可以识别，请只返回 JSON 对象，禁止输出展示文本、解释文字或 Markdown。"
                "对象字段必须包含：found(boolean)、query_name(string)、name(string)、"
                "display_name(string)、country_code(string)、latitude(number)、longitude(number)。"
                "display_name 请优先使用‘城市，中国’这类中文格式。"
                f"用户输入：{city}"
            )
        )

        if not payload.get("found", True):
            raise CityNotFoundError("未找到城市位置信息。")

        self._require_keys(
            payload,
            required_keys={"query_name", "name", "display_name", "country_code", "latitude", "longitude"},
        )

        try:
            latitude = self._to_float(payload.get("latitude"))
            longitude = self._to_float(payload.get("longitude"))
        except (TypeError, ValueError) as exc:
            raise WeatherServiceError("城市查询服务返回的数据不完整，请稍后再试。") from exc

        display_name = self.build_display_name(payload, city)
        return ResolvedCity(
            query_name=str(payload.get("query_name") or city).strip() or city,
            display_name=display_name,
            latitude=latitude,
            longitude=longitude,
            normalized_key=self.build_normalized_key(payload, latitude, longitude),
        )

    def get_weather_for_location(
        self,
        city_label: str,
        latitude: float,
        longitude: float,
        timezone: str,
    ) -> CityWeatherResult:
        payload = self._request_model_json(
            user_prompt=(
                "请根据给定城市和坐标，返回该城市今天到未来 6 天的天气。"
                "只返回 JSON 对象，禁止输出最终展示文本、解释文字、Markdown 或额外字段说明。"
                "返回字段必须严格包含：city(string)、current(object)、daily(array, 恰好 7 项)。"
                "current 字段必须包含：weather(string)、temperature(number)、"
                "apparent_temperature(number)、wind_speed(number)。"
                "daily 每项必须包含：date(YYYY-MM-DD)、weather(string)、"
                "temp_min(number)、temp_max(number)、precipitation_probability(number 0-100)。"
                f"城市：{city_label}；纬度：{latitude}；经度：{longitude}；时区：{timezone}。"
                "daily 要包含今天在内总共 7 天。"
            )
        )
        return self._build_city_weather(city=city_label, payload=payload)

    def get_weather_for_city_query(self, city: str, timezone: str) -> CityWeatherResult:
        resolved = self.resolve_city(city)
        report = self.get_weather_for_location(
            city_label=resolved.display_name,
            latitude=resolved.latitude,
            longitude=resolved.longitude,
            timezone=timezone,
        )
        report.city = resolved.display_name
        return report

    def _request_model_json(self, user_prompt: str) -> dict:
        if not self.api_key:
            raise WeatherServiceError("未配置 DeepSeek API Key。")

        body = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是天气数据助手。你的所有回答都必须是合法 JSON 对象。"
                        "禁止输出 Markdown 代码块，禁止输出给终端用户直接展示的自然语言文本。"
                    ),
                },
                {
                    "role": "user",
                    "content": user_prompt + "。请确保最终输出是可直接解析的 json object。",
                },
            ],
        }
        payload = json.dumps(body).encode("utf-8")
        request = Request(
            DEEPSEEK_API_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw_response = json.load(response)
        except HTTPError as exc:
            detail = self._read_error_body(exc)
            logger.warning("DeepSeek API HTTP error: %s", detail or exc.reason)
            raise WeatherServiceError("天气服务请求失败，请稍后再试。") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise WeatherServiceError("天气服务请求失败，请稍后再试。") from exc

        content = self._extract_message_content(raw_response)
        try:
            parsed = json.loads(self._strip_code_fence(content))
        except json.JSONDecodeError as exc:
            logger.warning("DeepSeek returned non-JSON content: %s", content)
            raise WeatherServiceError("天气服务返回的数据无法解析，请稍后再试。") from exc

        if not isinstance(parsed, dict):
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")
        return parsed

    def _build_city_weather(self, city: str, payload: dict) -> CityWeatherResult:
        self._require_keys(payload, required_keys={"city", "current", "daily"})

        current_payload = payload.get("current")
        daily_payload = payload.get("daily")

        if not isinstance(current_payload, dict) or not isinstance(daily_payload, list):
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")

        self._require_keys(current_payload, required_keys=EXPECTED_CURRENT_FIELDS)

        daily_items: list[dict] = []
        for item in daily_payload[:QUERY_FORECAST_DAYS]:
            if not isinstance(item, dict):
                raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")
            self._require_keys(item, required_keys=EXPECTED_DAILY_FIELDS)
            date_value = self._validate_date(item.get("date"))
            weather_text, weather_emoji = self.normalize_weather(item.get("weather"))
            daily_items.append(
                {
                    "date": date_value,
                    "weather": weather_text,
                    "weather_emoji": weather_emoji,
                    "temp_max": self._required_float(item.get("temp_max")),
                    "temp_min": self._required_float(item.get("temp_min")),
                    "precipitation_probability": self._clamp_percentage(
                        self._required_float(item.get("precipitation_probability"))
                    ),
                }
            )

        if len(daily_items) != QUERY_FORECAST_DAYS:
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")

        current_weather, current_emoji = self.normalize_weather(current_payload.get("weather"))
        return CityWeatherResult(
            city=str(payload.get("city") or city).strip() or city,
            current={
                "temperature": self._required_float(current_payload.get("temperature")),
                "apparent_temperature": self._required_float(
                    current_payload.get("apparent_temperature")
                ),
                "weather": current_weather,
                "weather_emoji": current_emoji,
                "wind_speed": self._required_float(current_payload.get("wind_speed")),
            },
            daily=daily_items,
        )

    @staticmethod
    def build_display_name(location: dict, fallback_name: str) -> str:
        display_name = str(location.get("display_name") or "").strip()
        if display_name:
            return display_name

        name = str(location.get("name") or fallback_name).strip() or fallback_name
        country = str(location.get("country") or "").strip()
        if country and country != name:
            return f"{name}，{country}"
        return name

    @staticmethod
    def build_normalized_key(location: dict, latitude: float, longitude: float) -> str:
        country_code = str(location.get("country_code") or "XX").upper()
        rounded_latitude = round(float(latitude), NORMALIZED_COORD_PRECISION)
        rounded_longitude = round(float(longitude), NORMALIZED_COORD_PRECISION)
        return (
            f"{country_code}:"
            f"{rounded_latitude:.{NORMALIZED_COORD_PRECISION}f}:"
            f"{rounded_longitude:.{NORMALIZED_COORD_PRECISION}f}"
        )

    @staticmethod
    def normalize_weather(value: object) -> tuple[str, str]:
        weather_text = str(value or "未知").strip() or "未知"
        for keywords, normalized in WEATHER_TEXT_ALIASES:
            if any(keyword in weather_text for keyword in keywords):
                return normalized
        return weather_text, "🌤️"

    @staticmethod
    def _extract_message_content(payload: dict) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")
        return content

    @staticmethod
    def _strip_code_fence(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return stripped

    @staticmethod
    def _read_error_body(error: HTTPError) -> str:
        try:
            return error.read().decode("utf-8", errors="ignore")
        except OSError:
            return ""

    @staticmethod
    def _require_keys(payload: dict, required_keys: set[str]) -> None:
        missing = [key for key in required_keys if key not in payload or payload.get(key) in (None, "")]
        if missing:
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")

    @staticmethod
    def _validate_date(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。") from exc
        return value

    @staticmethod
    def _to_float(value: object) -> float:
        return float(value)

    @staticmethod
    def _required_float(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。") from exc

    @staticmethod
    def _clamp_percentage(value: float) -> float:
        return max(0.0, min(100.0, value))
