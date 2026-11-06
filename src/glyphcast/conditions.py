"""WMO weather-code (Open-Meteo's `weather_code` field) -> icon kind +
intensity, independent of how that gets drawn (see icons.py)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IconKind(Enum):
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    OVERCAST = "overcast"
    FOG = "fog"
    RAIN = "rain"
    SNOW = "snow"
    THUNDERSTORM = "thunderstorm"


# code -> (kind, intensity 0..1 baseline before precip-driven adjustment)
_CODE_TABLE: dict[int, tuple[IconKind, float]] = {
    0: (IconKind.CLEAR, 1.0),
    1: (IconKind.CLEAR, 0.7),
    2: (IconKind.PARTLY_CLOUDY, 0.5),
    3: (IconKind.OVERCAST, 0.8),
    45: (IconKind.FOG, 0.6),
    48: (IconKind.FOG, 0.9),
    51: (IconKind.RAIN, 0.2),
    53: (IconKind.RAIN, 0.35),
    55: (IconKind.RAIN, 0.5),
    56: (IconKind.RAIN, 0.3),
    57: (IconKind.RAIN, 0.45),
    61: (IconKind.RAIN, 0.3),
    63: (IconKind.RAIN, 0.55),
    65: (IconKind.RAIN, 0.85),
    66: (IconKind.RAIN, 0.4),
    67: (IconKind.RAIN, 0.7),
    71: (IconKind.SNOW, 0.3),
    73: (IconKind.SNOW, 0.55),
    75: (IconKind.SNOW, 0.85),
    77: (IconKind.SNOW, 0.4),
    80: (IconKind.RAIN, 0.4),
    81: (IconKind.RAIN, 0.6),
    82: (IconKind.RAIN, 0.9),
    85: (IconKind.SNOW, 0.45),
    86: (IconKind.SNOW, 0.75),
    95: (IconKind.THUNDERSTORM, 0.7),
    96: (IconKind.THUNDERSTORM, 0.85),
    99: (IconKind.THUNDERSTORM, 1.0),
}

# (units, daily?) -> amount that counts as "saturate intensity to 1.0". Daily
# accumulations run well above an instantaneous/nowcast rate, so each gets
# its own scale; metric and imperial obviously aren't the same number in the
# same unit. Rough calibration, not a meteorological standard.
_RAIN_SCALE_REF = {
    ("metric", False): 5.0,    # mm, hourly nowcast -- 5mm/h ~ a solid downpour
    ("metric", True): 15.0,    # mm, daily total
    ("imperial", False): 0.2,  # inch, hourly nowcast
    ("imperial", True): 0.6,   # inch, daily total
}
_SNOW_SCALE_REF = {
    ("metric", False): 2.0,    # cm, hourly nowcast
    ("metric", True): 8.0,     # cm, daily total
    ("imperial", False): 0.8,  # inch, hourly nowcast
    ("imperial", True): 3.0,   # inch, daily total
}


@dataclass
class Condition:
    kind: IconKind
    intensity: float  # 0..1, how strongly to draw it
    wind_overlay: bool


def classify(
    code: int, rain_amount: float, snow_amount: float, wind_speed: float, cloud_cover: float,
    wind_threshold: float, units: str = "metric", daily: bool = False,
) -> Condition:
    kind, intensity = _CODE_TABLE.get(int(code), (IconKind.PARTLY_CLOUDY, 0.5))

    if kind in (IconKind.RAIN, IconKind.THUNDERSTORM) and rain_amount > 0:
        # Blend the code's baseline intensity with how much is actually
        # falling, so a "light rain" code during a heavier burst still
        # reads as heavier than a genuinely light one.
        ref = _RAIN_SCALE_REF[(units, daily)]
        intensity = max(intensity, min(1.0, rain_amount / ref))
    elif kind is IconKind.SNOW and snow_amount > 0:
        ref = _SNOW_SCALE_REF[(units, daily)]
        intensity = max(intensity, min(1.0, snow_amount / ref))
    elif kind in (IconKind.PARTLY_CLOUDY, IconKind.OVERCAST):
        intensity = max(intensity, min(1.0, cloud_cover / 100.0))

    return Condition(kind=kind, intensity=intensity, wind_overlay=wind_speed >= wind_threshold)
