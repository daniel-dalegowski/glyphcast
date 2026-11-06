"""Orchestrates: fetch weather -> classify -> composite (light + dark) ->
publish. Also provides the network-free `--mock` path used for testing and
tuning the icon designs (see cli.py)."""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image

from . import compositor, publish
from .conditions import Condition, IconKind, classify
from .weather import ForecastDay, WeatherApiError, WeatherNow, fetch, fetch_forecast

log = logging.getLogger("glyphcast")

MOCKS: dict[str, Condition] = {
    "clear": Condition(IconKind.CLEAR, 1.0, False),
    "partly-cloudy": Condition(IconKind.PARTLY_CLOUDY, 0.6, False),
    "overcast": Condition(IconKind.OVERCAST, 0.8, False),
    "fog": Condition(IconKind.FOG, 0.7, False),
    "rain1": Condition(IconKind.RAIN, 0.25, False),
    "rain2": Condition(IconKind.RAIN, 0.55, False),
    "rain3": Condition(IconKind.RAIN, 0.9, False),
    "snow": Condition(IconKind.SNOW, 0.6, False),
    "storm": Condition(IconKind.THUNDERSTORM, 0.9, False),
    "windy": Condition(IconKind.PARTLY_CLOUDY, 0.5, True),
}


def run(config, force: bool = False) -> bool:
    if config.layout == "forecast":
        return _run_forecast(config)
    return _run_current(config)


def _run_current(config) -> bool:
    try:
        w = fetch(
            config.latitude, config.longitude, config.units,
            config.temperature_unit, config.wind_speed_unit, config.precipitation_unit,
        )
    except WeatherApiError:
        log.exception("weather fetch failed; leaving current output in place")
        return False

    # current's gust field is the closest equivalent to the forecast path's
    # daily max gust -- use it for the same "is this windy" judgment.
    condition = classify(w.code, w.rain, w.snowfall, w.wind_gusts, w.cloud_cover,
                          config.wind_overlay_threshold, units=config.units)
    log.info(
        "weather: %s intensity=%.2f wind_overlay=%s temp=%s",
        condition.kind.value, condition.intensity, condition.wind_overlay,
        compositor.format_temp(w.temp, w.units),
    )

    build_fn = lambda base: compositor.build_overlay(base, w, condition, config)  # noqa: E731
    ok = _render_and_publish(build_fn, config, dark=False)
    if config.has_dark:
        ok = _render_and_publish(build_fn, config, dark=True) and ok
    return ok


def _run_forecast(config) -> bool:
    try:
        days = fetch_forecast(
            config.latitude, config.longitude, config.units,
            config.temperature_unit, config.wind_speed_unit, config.precipitation_unit,
            days=config.forecast_days,
        )
    except WeatherApiError:
        log.exception("forecast fetch failed; leaving current output in place")
        return False

    log.info("forecast: %s", ", ".join(f"{d.date}=code{d.code}" for d in days))

    build_fn = lambda base: compositor.build_forecast_overlay(base, days, config)  # noqa: E731
    ok = _render_and_publish(build_fn, config, dark=False)
    if config.has_dark:
        ok = _render_and_publish(build_fn, config, dark=True) and ok
    return ok


def _render_and_publish(build_fn, config, dark: bool) -> bool:
    base_path = Path(config.base_image_dark if dark else config.base_image).expanduser()
    out_path = Path(config.output_dark if dark else config.output).expanduser()
    if not base_path.is_file():
        log.error("base image not found: %s", base_path)
        return False
    try:
        data = compositor.render_variant(base_path, build_fn, dark=dark)
    except Exception:
        log.exception("render failed (dark=%s); leaving current output in place", dark)
        return False
    publish.atomic_write_bytes(data, out_path)
    log.info("published %s variant to %s", "dark" if dark else "light", out_path)
    return True


# Rotating set of WMO codes chosen to cover visually distinct icon kinds,
# for `render --forecast` -- not meant to resemble a real week.
_MOCK_FORECAST_CODES = [0, 2, 61, 65, 71, 95, 3]


def mock_forecast(units: str) -> list[ForecastDay]:
    today = date.today()
    base_hi = 20.0 if units == "metric" else 68.0
    rain_amt = 6.0 if units == "metric" else 0.24
    snow_amt = 3.0 if units == "metric" else 1.2
    days = []
    for i, code in enumerate(_MOCK_FORECAST_CODES):
        hi = base_hi - i * 1.5
        lo = hi - 8
        days.append(ForecastDay(
            date=(today + timedelta(days=i)).isoformat(), code=code, hi=hi, lo=lo,
            rain=rain_amt if code in (61, 65, 95) else 0.0,
            snowfall=snow_amt if code == 71 else 0.0,
            precip_probability=70.0 if code in (61, 65, 71, 95) else 10.0,
            wind_speed=12.0, wind_gusts=18.0,
        ))
    return days


def render_mock_forecast(config, base_path: Path) -> bytes:
    days = mock_forecast(config.units)
    base = Image.open(base_path).convert("RGB")
    overlay = compositor.build_forecast_overlay(base, days, config)
    buf = io.BytesIO()
    overlay.save(buf, "PNG")
    return buf.getvalue()


def mock_weather(units: str, temp: float = 18.0) -> WeatherNow:
    return WeatherNow(
        temp=temp, code=0, wind_speed=30.0, wind_gusts=42.0, rain=0.0, snowfall=0.0, cloud_cover=50.0,
        hi=temp + 4, lo=temp - 4, local_time=datetime.now(), units=units,
    )


def render_mock(name: str, config, base_path: Path) -> bytes:
    """Renders one mock condition against `base_path` directly -- bypasses
    the pristine-base hash cache entirely (that machinery exists for the
    hourly job's output==input case; a one-off test render has no such
    loop to protect against)."""
    if name not in MOCKS:
        raise ValueError(f"unknown mock condition {name!r}; choices: {', '.join(MOCKS)}")
    condition = MOCKS[name]
    w = mock_weather(config.units)
    base = Image.open(base_path).convert("RGB")
    overlay = compositor.build_overlay(base, w, condition, config)
    buf = io.BytesIO()
    overlay.save(buf, "PNG")
    return buf.getvalue()
