"""Client for Open-Meteo's forecast API (free, no API key) -- current
conditions plus a 7-day forecast, with rain/showers/snowfall requested
separately (rather than one blended precipitation total) and wind gusts
alongside sustained speed, so conditions.classify() can judge intensity
and "is this windy" from the right signal instead of one blunt number."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherApiError(RuntimeError):
    pass


@dataclass
class WeatherNow:
    temp: float
    code: int
    wind_speed: float
    wind_gusts: float
    rain: float  # rain + showers, current unit (mm or inch)
    snowfall: float  # current unit (cm or inch)
    cloud_cover: float
    hi: float
    lo: float
    local_time: datetime
    units: str  # "metric" | "imperial" -- which symbols to display (°C vs °F etc.)


def fetch(
    latitude: float, longitude: float, units: str,
    temperature_unit: str, wind_speed_unit: str, precipitation_unit: str,
    timeout: int = 10,
) -> WeatherNow:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,wind_speed_10m,wind_gusts_10m,rain,showers,snowfall,cloud_cover",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto",
        "temperature_unit": temperature_unit,
        "wind_speed_unit": wind_speed_unit,
        "precipitation_unit": precipitation_unit,
    }
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WeatherApiError(f"could not reach Open-Meteo: {exc}") from exc

    return parse_response(response.json(), units)


def parse_response(payload: dict, units: str) -> WeatherNow:
    try:
        current = payload["current"]
        daily = payload["daily"]
        return WeatherNow(
            temp=float(current["temperature_2m"]),
            code=int(current["weather_code"]),
            wind_speed=float(current["wind_speed_10m"]),
            wind_gusts=float(current["wind_gusts_10m"]),
            rain=float(current["rain"]) + float(current["showers"]),
            snowfall=float(current["snowfall"]),
            cloud_cover=float(current["cloud_cover"]),
            hi=float(daily["temperature_2m_max"][0]),
            lo=float(daily["temperature_2m_min"][0]),
            local_time=datetime.fromisoformat(current["time"]),
            units=units,
        )
    except (KeyError, IndexError) as exc:
        raise WeatherApiError(f"unexpected response shape: missing {exc}") from exc


@dataclass
class ForecastDay:
    date: str  # ISO 8601, e.g. "2026-11-05"
    code: int
    hi: float
    lo: float
    rain: float  # rain + showers, daily total, current unit (mm or inch)
    snowfall: float  # daily total, current unit (cm or inch)
    precip_probability: float  # 0-100, max over the day
    wind_speed: float  # daily max sustained
    wind_gusts: float  # daily max gust


def fetch_forecast(
    latitude: float, longitude: float, units: str,
    temperature_unit: str, wind_speed_unit: str, precipitation_unit: str,
    days: int = 7, timeout: int = 10,
) -> list[ForecastDay]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": (
            "temperature_2m_max,temperature_2m_min,weather_code,rain_sum,showers_sum,snowfall_sum,"
            "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max"
        ),
        "forecast_days": days,
        "timezone": "auto",
        "temperature_unit": temperature_unit,
        "wind_speed_unit": wind_speed_unit,
        "precipitation_unit": precipitation_unit,
    }
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WeatherApiError(f"could not reach Open-Meteo: {exc}") from exc

    return parse_forecast_response(response.json())


def parse_forecast_response(payload: dict) -> list[ForecastDay]:
    try:
        daily = payload["daily"]
        dates = daily["time"]
        return [
            ForecastDay(
                date=date,
                code=int(daily["weather_code"][i]),
                hi=float(daily["temperature_2m_max"][i]),
                lo=float(daily["temperature_2m_min"][i]),
                rain=float(daily["rain_sum"][i]) + float(daily["showers_sum"][i]),
                snowfall=float(daily["snowfall_sum"][i]),
                precip_probability=float(daily["precipitation_probability_max"][i]),
                wind_speed=float(daily["wind_speed_10m_max"][i]),
                wind_gusts=float(daily["wind_gusts_10m_max"][i]),
            )
            for i, date in enumerate(dates)
        ]
    except (KeyError, IndexError) as exc:
        raise WeatherApiError(f"unexpected response shape: missing {exc}") from exc
