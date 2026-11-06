"""Load ~/.config/glyphcast/config.toml, merged over defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field

from . import paths

DEFAULTS = {
    "latitude": 0.0,
    "longitude": 0.0,
    "units": "metric",  # metric | imperial -- drives temperature, wind speed, and precipitation units together
    "base_image": "~/.local/share/backgrounds/glyphscape/live.png",
    "base_image_dark": "~/.local/share/backgrounds/glyphscape/live-dark.png",  # "" disables dark variant
    "output": "~/.local/share/backgrounds/glyphscape/live.png",
    "output_dark": "~/.local/share/backgrounds/glyphscape/live-dark.png",
    "layout": "forecast",  # forecast (N-day strip) | current (today only, single big widget)
    "forecast_days": 7,
    "style": "glyph",  # glyph | plain
    "box": "980x190",  # overall widget size in pixels, "WxH"
    "icon_cell": "7x7",  # pixel size of one icon glyph cell
    "font": "DejaVu Sans",
    "text_font_size": 22,
    "label_font_size": 15,
    "precip_font_size": 14,
    "wind_overlay_threshold": 25,  # wind gust speed, km/h (metric) or mph (imperial), above which wind chevrons overlay
    "placement": {
        "mode": "below-art",  # below-art | quiet-region | corner | off
        "corner": "bottom-right",  # top-left | top-right | bottom-left | bottom-right
        "margin": 40,
    },
}

_ATTR_NAME_OVERRIDES = {}


def settable_keys() -> dict[str, str]:
    mapping = {}
    for key, value in DEFAULTS.items():
        if not isinstance(value, dict):
            mapping[key] = key
            continue
        for subkey, subvalue in value.items():
            if isinstance(subvalue, dict):
                continue
            dotted = f"{key}.{subkey}"
            mapping[dotted] = _ATTR_NAME_OVERRIDES.get(dotted, f"{key}_{subkey}")
    return mapping


@dataclass
class Config:
    latitude: float
    longitude: float
    units: str
    base_image: str
    base_image_dark: str
    output: str
    output_dark: str
    layout: str
    forecast_days: int
    style: str
    box: str
    icon_cell: str
    font: str
    text_font_size: int
    label_font_size: int
    precip_font_size: int
    wind_overlay_threshold: float
    placement_mode: str
    placement_corner: str
    placement_margin: int
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def box_wh(self) -> tuple[int, int]:
        w, h = self.box.lower().split("x")
        return int(w), int(h)

    @property
    def icon_cell_wh(self) -> tuple[int, int]:
        w, h = self.icon_cell.lower().split("x")
        return int(w), int(h)

    @property
    def has_dark(self) -> bool:
        return bool(self.base_image_dark.strip()) and bool(self.output_dark.strip())

    @property
    def temperature_unit(self) -> str:
        return "celsius" if self.units == "metric" else "fahrenheit"

    @property
    def wind_speed_unit(self) -> str:
        return "kmh" if self.units == "metric" else "mph"

    @property
    def precipitation_unit(self) -> str:
        return "mm" if self.units == "metric" else "inch"


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load() -> Config:
    data = dict(DEFAULTS)
    cfg_path = paths.config_file()
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            user_data = tomllib.load(f)
        data = _deep_merge(data, user_data)

    placement = data.get("placement", {})

    return Config(
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
        units=str(data["units"]),
        base_image=str(data["base_image"]),
        base_image_dark=str(data["base_image_dark"]),
        output=str(data["output"]),
        output_dark=str(data["output_dark"]),
        layout=str(data["layout"]),
        forecast_days=int(data["forecast_days"]),
        style=str(data["style"]),
        box=str(data["box"]),
        icon_cell=str(data["icon_cell"]),
        font=str(data["font"]),
        text_font_size=int(data["text_font_size"]),
        label_font_size=int(data["label_font_size"]),
        precip_font_size=int(data["precip_font_size"]),
        wind_overlay_threshold=float(data["wind_overlay_threshold"]),
        placement_mode=str(placement.get("mode", DEFAULTS["placement"]["mode"])),
        placement_corner=str(placement.get("corner", DEFAULTS["placement"]["corner"])),
        placement_margin=int(placement.get("margin", DEFAULTS["placement"]["margin"])),
        raw=data,
    )
