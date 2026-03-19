from dataclasses import dataclass
import hashlib
import logging
import time
from urllib.parse import urlencode

import httpx

from app.config import load_settings


logger = logging.getLogger(__name__)

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
REQUEST_TIMEOUT_SECONDS = 25.0
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.5
DISPLAY_FORECAST_DAYS = 3
MUNICIPALITY_CODES = {"11", "12", "31", "50"}
DISTRICT_SUFFIXES = ("区", "县", "旗", "镇", "乡", "街道", "新区", "开发区")
WEATHER_TEXT_ALIASES = [
    (("雷",), ("雷暴", "⛈️")),
    (("暴雨",), ("暴雨", "🌧️")),
    (("雨",), ("雨", "🌧️")),
    (("雪",), ("雪", "🌨️")),
    (("雾", "霾", "烟"), ("雾", "🌫️")),
    (("阴",), ("阴", "☁️")),
    (("多云",), ("多云", "⛅")),
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
    """Fetch current weather and forecast from AMap Web Service APIs."""

    def __init__(self) -> None:
        settings = load_settings()
        self.api_key = settings.amap_web_api_key
        self.api_secret = settings.amap_web_api_secret
        self.timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)

    def resolve_city(self, city: str) -> ResolvedCity:
        payload = self._request_amap_json(
            request_label="geocode",
            base_url=AMAP_GEOCODE_URL,
            params={"address": city, "output": "JSON"},
        )
        geocodes = payload.get("geocodes")
        if not isinstance(geocodes, list) or not geocodes:
            logger.warning("AMap geocode returned no geocodes for city query '%s'.", city)
            raise CityNotFoundError("未找到城市位置信息。")

        geocode = self.pick_best_geocode(city, geocodes)
        adcode = self.normalize_city_adcode(city, str(geocode.get("adcode") or "").strip())
        longitude, latitude = self.parse_location(geocode.get("location"))
        display_name = self.build_display_name(geocode, city)

        logger.info(
            "AMap geocode resolved '%s' -> display_name=%s, adcode=%s, level=%s",
            city,
            display_name,
            adcode,
            geocode.get("level"),
        )

        return ResolvedCity(
            query_name=city,
            display_name=display_name,
            latitude=latitude,
            longitude=longitude,
            normalized_key=self.build_normalized_key(adcode),
        )

    def get_weather_by_adcode(self, city_label: str, adcode: str) -> CityWeatherResult:
        current_payload = self._request_amap_json(
            request_label="weather_base",
            base_url=AMAP_WEATHER_URL,
            params={"city": adcode, "extensions": "base", "output": "JSON"},
        )
        forecast_payload = self._request_amap_json(
            request_label="weather_all",
            base_url=AMAP_WEATHER_URL,
            params={"city": adcode, "extensions": "all", "output": "JSON"},
        )
        return self._build_city_weather(city_label, adcode, current_payload, forecast_payload)

    def get_weather_for_city_query(self, city: str, timezone: str) -> CityWeatherResult:
        del timezone
        resolved = self.resolve_city(city)
        return self.get_weather_by_adcode(
            city_label=resolved.display_name,
            adcode=self.extract_adcode(resolved.normalized_key),
        )

    def _request_amap_json(self, request_label: str, base_url: str, params: dict[str, str]) -> dict:
        if not self.api_key:
            raise WeatherServiceError("未配置高德 Web 服务 Key。")

        request_params = dict(params)
        request_params["key"] = self.api_key
        if self.api_secret:
            request_params["sig"] = self.build_sig(base_url, request_params, self.api_secret)

        request_url = f"{base_url}?{urlencode(request_params)}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=self.timeout, http2=False) as client:
                    response = client.get(request_url)
                    response.raise_for_status()
                    payload = response.json()
                break
            except httpx.TimeoutException as exc:
                logger.warning(
                    "AMap %s timeout on attempt %s/%s: %s",
                    request_label,
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
            except httpx.NetworkError as exc:
                logger.warning(
                    "AMap %s network/SSL error on attempt %s/%s: %s",
                    request_label,
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "AMap %s HTTP status error on attempt %s/%s: status=%s",
                    request_label,
                    attempt,
                    MAX_RETRIES,
                    exc.response.status_code,
                )
            except ValueError as exc:
                logger.warning(
                    "AMap %s invalid JSON on attempt %s/%s: %s",
                    request_label,
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "AMap %s HTTP client error on attempt %s/%s: %s",
                    request_label,
                    attempt,
                    MAX_RETRIES,
                    exc,
                )

            if attempt == MAX_RETRIES:
                raise WeatherServiceError("天气服务暂时不可用，请稍后再试。")
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        status = str(payload.get("status") or "")
        info = str(payload.get("info") or "")
        infocode = str(payload.get("infocode") or "")
        reporttime = self.extract_reporttime(payload)
        logger.info(
            "AMap %s response: status=%s info=%s infocode=%s reporttime=%s",
            request_label,
            status,
            info,
            infocode,
            reporttime or "-",
        )

        if status != "1" or infocode != "10000":
            logger.warning(
                "AMap %s business error: status=%s info=%s infocode=%s",
                request_label,
                status,
                info,
                infocode,
            )
            raise WeatherServiceError("天气服务暂时不可用，请稍后再试。")

        return payload

    def _build_city_weather(
        self,
        city_label: str,
        adcode: str,
        current_payload: dict,
        forecast_payload: dict,
    ) -> CityWeatherResult:
        lives = current_payload.get("lives")
        forecasts = forecast_payload.get("forecasts")
        if not isinstance(lives, list) or not lives:
            logger.warning("AMap weather base returned empty lives for adcode=%s", adcode)
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")
        if not isinstance(forecasts, list) or not forecasts:
            logger.warning("AMap weather forecast returned empty forecasts for adcode=%s", adcode)
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")

        live = lives[0]
        forecast = forecasts[0]
        casts = forecast.get("casts")
        if not isinstance(casts, list) or not casts:
            logger.warning("AMap weather forecast returned empty casts for adcode=%s", adcode)
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")

        current_weather, current_emoji = self.normalize_weather(live.get("weather"))
        daily_items: list[dict] = []
        for cast in casts[:DISPLAY_FORECAST_DAYS]:
            if not isinstance(cast, dict):
                continue
            date_text = str(cast.get("date") or "").strip()
            day_weather, day_emoji = self.normalize_weather(cast.get("dayweather"))
            night_weather, night_emoji = self.normalize_weather(cast.get("nightweather"))
            daily_items.append(
                {
                    "date": date_text,
                    "weather": day_weather,
                    "weather_emoji": day_emoji,
                    "day_weather": day_weather,
                    "day_weather_emoji": day_emoji,
                    "night_weather": night_weather,
                    "night_weather_emoji": night_emoji,
                    "temp_max": self._safe_float(cast.get("daytemp")),
                    "temp_min": self._safe_float(cast.get("nighttemp")),
                    "day_wind": str(cast.get("daywind") or "").strip(),
                    "night_wind": str(cast.get("nightwind") or "").strip(),
                    "day_power": str(cast.get("daypower") or "").strip(),
                    "night_power": str(cast.get("nightpower") or "").strip(),
                }
            )

        logger.info(
            "AMap forecast dates for %s: %s",
            city_label,
            [item.get("date") for item in daily_items],
        )

        if not daily_items:
            raise WeatherServiceError("天气服务返回的数据不完整，请稍后再试。")

        return CityWeatherResult(
            city=city_label,
            current={
                "temperature": self._safe_float(live.get("temperature")),
                "weather": current_weather,
                "weather_emoji": current_emoji,
                "wind_direction": str(live.get("winddirection") or "").strip(),
                "wind_power": str(live.get("windpower") or "").strip(),
                "humidity": str(live.get("humidity") or "").strip(),
                "report_time": str(live.get("reporttime") or forecast.get("reporttime") or "").strip(),
            },
            daily=daily_items,
        )

    @staticmethod
    def pick_best_geocode(query: str, geocodes: list[dict]) -> dict:
        normalized_query = query.strip()
        explicit_district = normalized_query.endswith(DISTRICT_SUFFIXES)
        if explicit_district:
            return geocodes[0]

        level_priority = {"city": 0, "district": 1, "province": 2, "street": 3}
        return sorted(
            geocodes,
            key=lambda item: level_priority.get(str(item.get("level") or ""), 99),
        )[0]

    @staticmethod
    def normalize_city_adcode(query: str, adcode: str) -> str:
        if not adcode or len(adcode) != 6 or not adcode.isdigit():
            raise CityNotFoundError("未找到城市位置信息。")

        explicit_district = query.strip().endswith(DISTRICT_SUFFIXES)
        if explicit_district:
            return adcode

        prefix = adcode[:2]
        if prefix in MUNICIPALITY_CODES:
            return prefix + "0100"
        return adcode[:4] + "00"

    @staticmethod
    def parse_location(location: object) -> tuple[float, float]:
        if not isinstance(location, str) or "," not in location:
            return 0.0, 0.0
        longitude_text, latitude_text = location.split(",", 1)
        try:
            return float(longitude_text), float(latitude_text)
        except ValueError:
            return 0.0, 0.0

    @staticmethod
    def build_display_name(geocode: dict, fallback_name: str) -> str:
        district = str(geocode.get("district") or "").strip()
        city = geocode.get("city")
        province = str(geocode.get("province") or "").strip()
        city_text = city if isinstance(city, str) else ""
        city_text = city_text.strip()

        if city_text:
            return city_text
        if district and province and district != province:
            return f"{district}，{province}"
        if province:
            return province
        return fallback_name

    @staticmethod
    def build_normalized_key(adcode: str) -> str:
        return f"adcode:{adcode}"

    @staticmethod
    def extract_adcode(normalized_key: str | None) -> str:
        if not normalized_key or not normalized_key.startswith("adcode:"):
            raise CityNotFoundError("未找到城市位置信息。")
        return normalized_key.split(":", 1)[1]

    @staticmethod
    def extract_reporttime(payload: dict) -> str | None:
        lives = payload.get("lives")
        if isinstance(lives, list) and lives:
            reporttime = lives[0].get("reporttime")
            if isinstance(reporttime, str) and reporttime.strip():
                return reporttime.strip()
        forecasts = payload.get("forecasts")
        if isinstance(forecasts, list) and forecasts:
            reporttime = forecasts[0].get("reporttime")
            if isinstance(reporttime, str) and reporttime.strip():
                return reporttime.strip()
        return None

    @staticmethod
    def normalize_weather(value: object) -> tuple[str, str]:
        weather_text = str(value or "未知").strip() or "未知"
        for keywords, normalized in WEATHER_TEXT_ALIASES:
            if any(keyword in weather_text for keyword in keywords):
                return normalized
        return weather_text, "🌤️"

    @staticmethod
    def build_sig(base_url: str, params: dict[str, str], secret: str) -> str:
        sorted_items = sorted((key, str(value)) for key, value in params.items())
        query = urlencode(sorted_items)
        raw = f"{base_url}?{query}{secret}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_float(value: object) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
