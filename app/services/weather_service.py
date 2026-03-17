from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


NORMALIZED_COORD_PRECISION = 4

WEATHER_CODE_DESCRIPTIONS = {
    0: "晴",
    1: "晴间多云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "冻雾",
    51: "小毛雨",
    53: "毛雨",
    55: "强毛雨",
    56: "冻毛雨",
    57: "强冻毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "冰粒",
    80: "阵雨",
    81: "强阵雨",
    82: "暴雨",
    85: "阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}

WEATHER_CODE_EMOJIS = {
    0: "☀️",
    1: "🌤️",
    2: "⛅",
    3: "☁️",
    45: "🌫️",
    48: "🌫️",
    51: "🌦️",
    53: "🌦️",
    55: "🌧️",
    61: "🌧️",
    63: "🌧️",
    65: "🌧️",
    71: "🌨️",
    73: "🌨️",
    75: "❄️",
    80: "🌦️",
    81: "🌧️",
    82: "🌧️",
    95: "⛈️",
    96: "⛈️",
    99: "⛈️",
}


class WeatherServiceError(Exception):
    """Raised when weather data cannot be fetched."""


class CityNotFoundError(WeatherServiceError):
    """Raised when a city cannot be resolved by geocoding."""


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
    """Fetch current weather and 7-day forecast for stored cities."""

    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    forecast_url = "https://api.open-meteo.com/v1/forecast"

    def resolve_city(self, city: str) -> ResolvedCity:
        location = self._get_city_location(city)
        return ResolvedCity(
            query_name=city,
            display_name=self.build_display_name(location),
            latitude=float(location["latitude"]),
            longitude=float(location["longitude"]),
            normalized_key=self.build_normalized_key(location),
        )

    def get_weather_for_location(
        self,
        city_label: str,
        latitude: float,
        longitude: float,
        timezone: str,
    ) -> CityWeatherResult:
        forecast = self._get_forecast(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
        )
        return self._build_city_weather(city=city_label, forecast=forecast)

    def _get_city_location(self, city: str) -> dict:
        payload = self._request_json(
            self.geocoding_url,
            {
                "name": city,
                "count": 1,
                "language": "zh",
                "format": "json",
            },
        )

        results = payload.get("results") or []
        if not results:
            raise CityNotFoundError("未找到城市位置信息。")

        return results[0]

    def _get_forecast(self, latitude: float, longitude: float, timezone: str) -> dict:
        return self._request_json(
            self.forecast_url,
            {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": timezone,
                "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": ",".join(
                    [
                        "weather_code",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_probability_max",
                    ]
                ),
                "forecast_days": 7,
            },
        )

    def _request_json(self, base_url: str, params: dict) -> dict:
        request_url = f"{base_url}?{urlencode(params)}"

        try:
            with urlopen(request_url, timeout=10) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise WeatherServiceError("天气服务请求失败，请稍后再试。") from exc

    def _build_city_weather(self, city: str, forecast: dict) -> CityWeatherResult:
        current = forecast.get("current")
        daily = forecast.get("daily")

        if not current or not daily:
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")

        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precipitation = daily.get("precipitation_probability_max", [])

        daily_items: list[dict] = []
        for index, date_value in enumerate(dates):
            code = codes[index] if index < len(codes) else None
            daily_items.append(
                {
                    "date": date_value,
                    "weather": self.describe_weather_code(code),
                    "weather_emoji": self.get_weather_emoji(code),
                    "temp_max": max_temps[index] if index < len(max_temps) else None,
                    "temp_min": min_temps[index] if index < len(min_temps) else None,
                    "precipitation_probability": (
                        precipitation[index] if index < len(precipitation) else None
                    ),
                }
            )

        current_code = current.get("weather_code")
        return CityWeatherResult(
            city=city,
            current={
                "temperature": current.get("temperature_2m"),
                "apparent_temperature": current.get("apparent_temperature"),
                "weather": self.describe_weather_code(current_code),
                "weather_emoji": self.get_weather_emoji(current_code),
                "wind_speed": current.get("wind_speed_10m"),
            },
            daily=daily_items,
        )

    @staticmethod
    def build_display_name(location: dict) -> str:
        name = str(location.get("name") or "").strip()
        country = str(location.get("country") or "").strip()
        admin1 = str(location.get("admin1") or "").strip()

        if country and country != name:
            return f"{name}，{country}"
        if admin1 and admin1 != name:
            return f"{name}，{admin1}"
        return name or "未知城市"

    @staticmethod
    def build_normalized_key(location: dict) -> str:
        location_id = location.get("id")
        if location_id is not None:
            return f"id:{location_id}"

        country_code = str(location.get("country_code") or "XX").upper()
        latitude = round(float(location["latitude"]), NORMALIZED_COORD_PRECISION)
        longitude = round(float(location["longitude"]), NORMALIZED_COORD_PRECISION)
        return (
            f"{country_code}:"
            f"{latitude:.{NORMALIZED_COORD_PRECISION}f}:"
            f"{longitude:.{NORMALIZED_COORD_PRECISION}f}"
        )

    @staticmethod
    def describe_weather_code(code: int | None) -> str:
        if code is None:
            return "未知"
        return WEATHER_CODE_DESCRIPTIONS.get(code, "未知")

    @staticmethod
    def get_weather_emoji(code: int | None) -> str:
        if code is None:
            return "❓"
        return WEATHER_CODE_EMOJIS.get(code, "🌤️")
