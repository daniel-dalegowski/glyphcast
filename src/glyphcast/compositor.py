"""Builds the weather widget and pastes it onto a copy of the pristine base
image. Owns the hash-cached pristine-base mechanism that lets `output` and
`base_image` be the *same* file (the normal case -- writing back onto
Glyphscape's own live.png) without ever stamping weather on top of its own
last stamp (see the plan's "Solving accumulation" section)."""

from __future__ import annotations

import functools
import hashlib
import io
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont, ImageStat

from . import density, icons, paths, placement
from .conditions import Condition, IconKind, classify
from .weather import ForecastDay, WeatherNow

BACKDROP_DARKEN = 0.45
FG_LIGHT = (245, 245, 245)
FG_DARK = (15, 15, 15)
ACCENT_COLOR = (255, 210, 90)
PAD = 16
DROPLET_WIDTH_RATIO = 0.68  # hand-drawn teardrop's width as a fraction of its height
PRECIP_EPSILON = 0.05  # amounts below this (mm or inch) are treated as "none" for display

PLAIN_ICONS: dict[IconKind, str] = {
    IconKind.CLEAR: "*",
    IconKind.PARTLY_CLOUDY: "o",
    IconKind.OVERCAST: "O",
    IconKind.FOG: "~",
    IconKind.RAIN: "/",
    IconKind.SNOW: "x",
    IconKind.THUNDERSTORM: "!",
}


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@functools.lru_cache(maxsize=8)
def resolve_font_path(spec: str) -> str:
    if spec.lower().endswith((".ttf", ".otf", ".ttc")):
        return spec
    if shutil.which("fc-match"):
        out = subprocess.run(
            ["fc-match", "-f", "%{file}", spec], capture_output=True, text=True, timeout=5, check=True
        ).stdout
        if out:
            return out
    raise FileNotFoundError(f"could not resolve font {spec!r} (no fc-match, and not a file path)")


def format_temp(value: float, units: str) -> str:
    symbol = "°C" if units == "metric" else "°F"
    return f"{round(value)}{symbol}"


def format_precip(amount: float, units: str) -> str:
    unit = "mm" if units == "metric" else "in"
    if amount >= 10:
        return f"{round(amount)}{unit}"
    value = round(amount, 1)
    if value == int(value):
        return f"{int(value)}{unit}"
    return f"{value}{unit}"


def _draw_droplet(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float, fill: tuple[int, int, int]) -> None:
    """A hand-drawn teardrop (pointed cap + circle), centered at (cx, cy)
    with total height `size` -- a Unicode water-drop glyph (U+1F4A7) isn't
    actually in DejaVu Sans and silently renders as a blank tofu box there,
    and none of the symbols that *do* render (triangles, umbrellas) read as
    "droplet" at a glance. Drawing the shape directly sidesteps font
    coverage entirely."""
    r = size * 0.34
    apex = (cx, cy - size / 2)
    circle_cy = cy + size / 2 - r
    draw.polygon(
        [apex, (cx - r * 0.98, circle_cy - r * 0.12), (cx + r * 0.98, circle_cy - r * 0.12)], fill=fill
    )
    draw.ellipse([cx - r, circle_cy - r, cx + r, circle_cy + r], fill=fill)


def _precip_amount(day: ForecastDay, condition: Condition) -> float:
    """Whichever amount matches the day's classified condition -- a day
    classified as snow shows its snowfall total, not a stray trace of rain
    that didn't change the classification, and vice versa."""
    if condition.kind in (IconKind.RAIN, IconKind.THUNDERSTORM):
        return day.rain
    if condition.kind is IconKind.SNOW:
        return day.snowfall
    return 0.0


def resolve_pristine(base_image_path: Path, dark: bool) -> Image.Image:
    """If base_image_path's current bytes match what we ourselves last wrote
    to `output`, nothing external has touched it -- reuse the cached
    pristine frame. Otherwise this is a fresh frame (first run, or
    Glyphscape/anything else just rewrote it) -- cache it as the new
    pristine base."""
    data = base_image_path.read_bytes()
    current_hash = sha256_bytes(data)

    hash_file = paths.output_hash_file(dark)
    pristine_file = paths.pristine_png(dark)
    last_output_hash = hash_file.read_text().strip() if hash_file.exists() else None

    if last_output_hash == current_hash and pristine_file.exists():
        return Image.open(pristine_file).convert("RGB")

    pristine_file.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.save(pristine_file)
    return img


def record_output_hash(data: bytes, dark: bool) -> None:
    hash_file = paths.output_hash_file(dark)
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(sha256_bytes(data))


def _draw_glyph_icon(draw: ImageDraw.ImageDraw, x0: int, y0: int, size: int, cell: tuple[int, int],
                      condition: Condition, font_path: str, ink: tuple[int, int, int]) -> None:
    cell_w, cell_h = cell
    cols, rows = max(1, size // cell_w), max(1, size // cell_h)

    grid, accent_cells = icons.build(condition.kind, condition.intensity, cols, rows)
    wind_cells: set[tuple[int, int]] = set()
    if condition.wind_overlay:
        wind_grid = icons.wind(cols, rows, speed_weight=0.7)
        grid, wind_cells = icons.compose_wind(grid, wind_grid)

    icon_font = ImageFont.truetype(font_path, cell_h)
    bins = density.build_bins(icons.VOCAB[condition.kind], icon_font, num_bins=6)
    wind_bins = density.build_bins(icons.WIND_VOCAB, icon_font, num_bins=6) if wind_cells else None
    rng = random.Random()

    for r in range(rows):
        recent: list[str] = []
        for c in range(cols):
            cx = x0 + c * cell_w + cell_w / 2
            cy = y0 + r * cell_h + cell_h / 2
            if (r, c) in accent_cells:
                draw.text((cx, cy), icons.ACCENT_CHAR, font=icon_font, fill=ACCENT_COLOR, anchor="mm")
                continue
            active_bins = wind_bins if (r, c) in wind_cells else bins
            ch = density.pick(active_bins, grid[r][c], rng, avoid=set(recent[-2:]))
            recent.append(ch)
            if ch != " ":
                draw.text((cx, cy), ch, font=icon_font, fill=ink, anchor="mm")


def build_overlay(base: Image.Image, weather: WeatherNow, condition: Condition, config) -> Image.Image:
    img = base.copy()
    box_w, box_h = config.box_wh
    pos = placement.find_box_position(
        img, box_w, box_h, config.placement_mode, config.placement_corner, config.placement_margin
    )
    if pos is None:
        return img

    x0, y0 = pos
    x0 = min(max(0, x0), max(0, img.width - box_w))
    y0 = min(max(0, y0), max(0, img.height - box_h))

    draw = ImageDraw.Draw(img)
    region = img.crop((x0, y0, x0 + box_w, y0 + box_h))
    avg_bg = tuple(round(v) for v in ImageStat.Stat(region).mean[:3])
    backdrop = tuple(round(v * BACKDROP_DARKEN) for v in avg_bg)
    ink = FG_LIGHT if _luminance(backdrop) < 128 else FG_DARK

    draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=backdrop)

    font_path = resolve_font_path(config.font)
    icon_size = box_h - 2 * PAD
    text_x = x0 + PAD * 2 + icon_size

    if config.style == "glyph":
        _draw_glyph_icon(draw, x0 + PAD, y0 + PAD, icon_size, config.icon_cell_wh, condition, font_path, ink)
    else:
        plain_font = ImageFont.truetype(font_path, icon_size)
        draw.text((x0 + PAD + icon_size / 2, y0 + box_h / 2), PLAIN_ICONS[condition.kind],
                   font=plain_font, fill=ink, anchor="mm")

    text_font = ImageFont.truetype(font_path, config.text_font_size)
    label_font = ImageFont.truetype(font_path, config.label_font_size)
    temp_str = format_temp(weather.temp, weather.units)
    label_str = f"{weather.local_time.strftime('%a').upper()} · {weather.local_time.strftime('%b %d')}"

    draw.text((text_x, y0 + box_h * 0.40), temp_str, font=text_font, fill=ink, anchor="lm")
    draw.text((text_x, y0 + box_h * 0.72), label_str, font=label_font, fill=ink, anchor="lm")

    return img


def _day_label(date_str: str, index: int) -> str:
    if index == 0:
        return "TODAY"
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a").upper()


def _forecast_condition(day: ForecastDay, wind_threshold: float, units: str) -> Condition:
    # Daily cloud_cover isn't fetched (classify only uses it to nudge
    # sun/cloud intensity, not to pick the kind) -- 50 is a neutral stand-in.
    # Gusts, not sustained speed, decide the wind overlay -- a gusty day
    # reads as "windy" even if the sustained speed alone wouldn't cross
    # the threshold.
    return classify(day.code, day.rain, day.snowfall, day.wind_gusts, cloud_cover=50.0,
                     wind_threshold=wind_threshold, units=units, daily=True)


def _draw_forecast_column(draw: ImageDraw.ImageDraw, x0: float, y0: float, col_w: float, col_h: float,
                           day: ForecastDay, index: int, config, font_path: str, ink: tuple[int, int, int]) -> None:
    label_font = ImageFont.truetype(font_path, config.label_font_size)
    temp_font = ImageFont.truetype(font_path, config.text_font_size)
    precip_font = ImageFont.truetype(font_path, config.precip_font_size)
    label_h = config.label_font_size * 1.5
    temp_h = config.text_font_size * 1.4
    precip_h = config.precip_font_size * 1.5
    icon_h = max(8.0, col_h - label_h - temp_h - precip_h)
    icon_size = max(8, int(min(col_w - 6, icon_h)))

    cx = x0 + col_w / 2
    draw.text((cx, y0 + label_h / 2), _day_label(day.date, index), font=label_font, fill=ink, anchor="mm")

    icon_x0 = x0 + (col_w - icon_size) / 2
    icon_y0 = y0 + label_h + (icon_h - icon_size) / 2
    condition = _forecast_condition(day, config.wind_overlay_threshold, config.units)
    _draw_glyph_icon(draw, icon_x0, icon_y0, icon_size, config.icon_cell_wh, condition, font_path, ink)

    temp_str = f"{round(day.hi)}°/{round(day.lo)}°"
    temp_y = y0 + label_h + icon_h + temp_h / 2
    draw.text((cx, temp_y), temp_str, font=temp_font, fill=ink, anchor="mm")

    amount = _precip_amount(day, condition)
    if amount > PRECIP_EPSILON:
        precip_str = format_precip(amount, config.units)
        row_cy = y0 + label_h + icon_h + temp_h + precip_h / 2
        droplet_size = config.precip_font_size * 0.85
        droplet_w = droplet_size * DROPLET_WIDTH_RATIO
        gap = 4
        text_w = draw.textlength(precip_str, font=precip_font)
        start_x = cx - (droplet_w + gap + text_w) / 2
        _draw_droplet(draw, start_x + droplet_w / 2, row_cy, droplet_size, ink)
        draw.text((start_x + droplet_w + gap, row_cy), precip_str, font=precip_font, fill=ink, anchor="lm")


def build_forecast_overlay(base: Image.Image, forecast: list[ForecastDay], config) -> Image.Image:
    img = base.copy()
    box_w, box_h = config.box_wh
    pos = placement.find_box_position(
        img, box_w, box_h, config.placement_mode, config.placement_corner, config.placement_margin
    )
    if pos is None:
        return img

    x0, y0 = pos
    x0 = min(max(0, x0), max(0, img.width - box_w))
    y0 = min(max(0, y0), max(0, img.height - box_h))

    draw = ImageDraw.Draw(img)
    region = img.crop((x0, y0, x0 + box_w, y0 + box_h))
    avg_bg = tuple(round(v) for v in ImageStat.Stat(region).mean[:3])
    backdrop = tuple(round(v * BACKDROP_DARKEN) for v in avg_bg)
    ink = FG_LIGHT if _luminance(backdrop) < 128 else FG_DARK
    draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=backdrop)

    font_path = resolve_font_path(config.font)
    n = max(1, len(forecast))
    gap = 6
    col_w = (box_w - 2 * PAD - (n - 1) * gap) / n
    for i, day in enumerate(forecast):
        cx0 = x0 + PAD + i * (col_w + gap)
        _draw_forecast_column(draw, cx0, y0 + PAD, col_w, box_h - 2 * PAD, day, i, config, font_path, ink)

    return img


def render_variant(base_image_path: Path, build_fn: Callable[[Image.Image], Image.Image], dark: bool) -> bytes:
    base = resolve_pristine(base_image_path, dark)
    overlay = build_fn(base)
    buf = io.BytesIO()
    overlay.save(buf, "PNG")
    data = buf.getvalue()
    record_output_hash(data, dark)
    return data
