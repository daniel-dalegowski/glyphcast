import pytest

from glyphcast.weather import WeatherApiError, parse_forecast_response, parse_response

SAMPLE_CURRENT = {
    "current": {
        "time": "2026-11-05T14:00",
        "temperature_2m": 12.3,
        "weather_code": 61,
        "wind_speed_10m": 14.0,
        "wind_gusts_10m": 22.0,
        "rain": 0.4,
        "showers": 0.0,
        "snowfall": 0.0,
        "cloud_cover": 80.0,
    },
    "daily": {
        "temperature_2m_max": [15.0],
        "temperature_2m_min": [8.0],
    },
}

SAMPLE_FORECAST = {
    "daily": {
        "time": ["2026-11-05", "2026-11-06"],
        "weather_code": [3, 61],
        "temperature_2m_max": [15.9, 19.7],
        "temperature_2m_min": [5.0, 5.5],
        "rain_sum": [0.0, 1.8],
        "showers_sum": [0.0, 0.1],
        "snowfall_sum": [0.0, 0.0],
        "precipitation_probability_max": [5, 88],
        "wind_speed_10m_max": [11.6, 18.4],
        "wind_gusts_10m_max": [15.8, 46.8],
    },
}


def test_parse_response():
    w = parse_response(SAMPLE_CURRENT, units="metric")
    assert w.temp == 12.3
    assert w.code == 61
    assert w.wind_speed == 14.0
    assert w.wind_gusts == 22.0
    assert w.rain == 0.4
    assert w.snowfall == 0.0
    assert w.cloud_cover == 80.0
    assert w.hi == 15.0
    assert w.lo == 8.0
    assert w.units == "metric"


def test_parse_response_missing_field_raises():
    broken = {"current": {"temperature_2m": 1.0}, "daily": SAMPLE_CURRENT["daily"]}
    with pytest.raises(WeatherApiError):
        parse_response(broken, units="metric")


def test_parse_forecast_response():
    days = parse_forecast_response(SAMPLE_FORECAST)
    assert len(days) == 2
    assert days[0].date == "2026-11-05"
    assert days[0].code == 3
    assert days[1].code == 61
    assert days[1].rain == pytest.approx(1.9)  # rain_sum + showers_sum
    assert days[1].precip_probability == 88
    assert days[1].wind_gusts == 46.8


def test_parse_forecast_response_missing_field_raises():
    broken = {"daily": {"time": ["2026-11-05"]}}
    with pytest.raises(WeatherApiError):
        parse_forecast_response(broken)
