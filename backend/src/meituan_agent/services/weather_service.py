from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class WeatherSnapshot:
    temperature_c: float | None
    precipitation_mm: float | None
    wind_kph: float | None
    weather_code: int | None
    is_day: bool | None
    fetched_at: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "temperature_c": self.temperature_c,
            "precipitation_mm": self.precipitation_mm,
            "wind_kph": self.wind_kph,
            "weather_code": self.weather_code,
            "is_day": self.is_day,
            "fetched_at": self.fetched_at,
        }


class WeatherService:
    def __init__(self, *, ttl_seconds: int = 1800) -> None:
        self._ttl = ttl_seconds

    def fetch(self, *, lat: float, lng: float) -> WeatherSnapshot | None:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "current": "temperature_2m,precipitation,weather_code,wind_speed_10m,is_day",
            "timezone": "auto",
        }
        now = int(time.time())
        try:
            with httpx.Client(timeout=8) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
        except Exception:
            return None

        cur = data.get("current") or {}
        try:
            temp = float(cur.get("temperature_2m")) if cur.get("temperature_2m") is not None else None
        except Exception:
            temp = None
        try:
            pr = float(cur.get("precipitation")) if cur.get("precipitation") is not None else None
        except Exception:
            pr = None
        try:
            wind = float(cur.get("wind_speed_10m")) if cur.get("wind_speed_10m") is not None else None
        except Exception:
            wind = None
        try:
            code = int(cur.get("weather_code")) if cur.get("weather_code") is not None else None
        except Exception:
            code = None
        is_day = None
        if cur.get("is_day") is not None:
            is_day = bool(int(cur.get("is_day")))

        return WeatherSnapshot(
            temperature_c=temp,
            precipitation_mm=pr,
            wind_kph=wind,
            weather_code=code,
            is_day=is_day,
            fetched_at=now,
        )

    def should_refresh(self, existing: dict[str, Any] | None) -> bool:
        if not existing:
            return True
        ts = existing.get("fetched_at")
        if not isinstance(ts, int):
            return True
        return int(time.time()) - ts >= self._ttl


def is_bad_outdoor(weather: dict[str, Any] | None) -> bool:
    if not weather:
        return False
    pr = weather.get("precipitation_mm")
    code = weather.get("weather_code")
    temp = weather.get("temperature_c")
    if isinstance(pr, (int, float)) and pr >= 0.2:
        return True
    if isinstance(code, int) and code >= 51:
        return True
    if isinstance(temp, (int, float)) and temp >= 32:
        return True
    return False

