from glyphcast.compositor import PRECIP_EPSILON, _precip_amount, format_precip
from glyphcast.conditions import Condition, IconKind
from glyphcast.weather import ForecastDay


def _day(rain=0.0, snowfall=0.0):
    return ForecastDay(date="2026-11-05", code=0, hi=10.0, lo=0.0, rain=rain, snowfall=snowfall,
                        precip_probability=0.0, wind_speed=0.0, wind_gusts=0.0)


def test_format_precip_metric_small_amount_keeps_a_decimal():
    assert format_precip(0.6, "metric") == "0.6mm"


def test_format_precip_metric_whole_number_drops_decimal():
    assert format_precip(2.0, "metric") == "2mm"


def test_format_precip_metric_large_amount_rounds_to_whole():
    assert format_precip(14.3, "metric") == "14mm"


def test_format_precip_imperial_uses_inches():
    assert format_precip(0.2, "imperial") == "0.2in"


def test_precip_amount_uses_rain_for_rain_kind():
    day = _day(rain=3.2, snowfall=1.0)  # stray snowfall shouldn't leak into a rain day's label
    condition = Condition(kind=IconKind.RAIN, intensity=0.5, wind_overlay=False)
    assert _precip_amount(day, condition) == 3.2


def test_precip_amount_uses_snowfall_for_snow_kind():
    day = _day(rain=0.3, snowfall=4.0)  # stray rain shouldn't leak into a snow day's label
    condition = Condition(kind=IconKind.SNOW, intensity=0.5, wind_overlay=False)
    assert _precip_amount(day, condition) == 4.0


def test_precip_amount_is_zero_for_non_precip_kinds():
    day = _day(rain=0.3, snowfall=0.1)  # trace amounts that didn't change the classified kind
    condition = Condition(kind=IconKind.OVERCAST, intensity=0.5, wind_overlay=False)
    assert _precip_amount(day, condition) == 0.0


def test_precip_epsilon_filters_trace_amounts():
    assert 0.02 < PRECIP_EPSILON
