"""Procedural density-weight grids per weather condition, plus the small
glyph vocabulary each one draws from. A weight grid is rows x cols of floats
in [0, 1] -- 0 picks from density.py's sparsest/blank bin, 1 the densest.

These are deliberately simple closed-form patterns (radial falloff, diagonal
streaks, seeded scatter) rather than anything photographic -- a first design
pass meant to be looked at and iterated on, same way Glyphscape's own glyph
system evolved past its original spec."""

from __future__ import annotations

import math
import random

from .conditions import IconKind

VOCAB: dict[IconKind, str] = {
    IconKind.CLEAR: " .'∘○◦•●",
    IconKind.PARTLY_CLOUDY: " .∘○◦•●▪▫",
    IconKind.OVERCAST: " ·∴▪▫□■",
    IconKind.FOG: " ·∴⦂≈~",
    IconKind.RAIN: " .'|╲",
    IconKind.SNOW: " .*+x",
    IconKind.THUNDERSTORM: " .'|╲",
}
WIND_VOCAB = " .-~>»"
ACCENT_CHAR = "*"  # the storm-bolt flash, drawn in its own accent color


def _rain_tier(intensity: float) -> int:
    return 1 if intensity < 0.4 else 2 if intensity < 0.7 else 3


def sun(cols: int, rows: int, intensity: float) -> list[list[float]]:
    cx, cy = (cols - 1) / 2.0, (rows - 1) / 2.0
    max_r = min(cols, rows) / 2.0 or 1.0
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            dx, dy = c - cx, r - cy
            d = math.hypot(dx, dy)
            base = max(0.0, 1.0 - d / max_r)
            rays = abs(math.cos(math.atan2(dy, dx) * 6))
            w = min(1.0, base**1.2 + 0.2 * rays * base) * (0.5 + 0.5 * intensity)
            row.append(w)
        grid.append(row)
    return grid


def cloud(cols: int, rows: int, cover: float) -> list[list[float]]:
    blobs = [
        (cols * 0.35, rows * 0.45, max(cols, rows) * 0.32),
        (cols * 0.62, rows * 0.55, max(cols, rows) * 0.30),
        (cols * 0.5, rows * 0.3, max(cols, rows) * 0.22),
    ]
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            best = 0.0
            for bx, by, br in blobs:
                d = math.hypot(c - bx, r - by)
                best = max(best, max(0.0, 1.0 - d / br))
            row.append(min(1.0, best) * (0.35 + 0.65 * cover))
        grid.append(row)
    return grid


def fog(cols: int, rows: int, intensity: float) -> list[list[float]]:
    base = 0.45 + 0.3 * intensity
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            band = 0.8 + 0.2 * math.sin(r * 1.3)
            drift = 0.9 + 0.1 * math.sin(c * 0.9 + r * 0.4)
            row.append(min(1.0, base * band * drift))
        grid.append(row)
    return grid


def rain(cols: int, rows: int, intensity: float) -> list[list[float]]:
    tier = _rain_tier(intensity)
    period = {1: 5, 2: 3, 3: 2}[tier]
    thickness = {1: 1, 2: 1, 3: 2}[tier]
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            diag = (c - r) % period
            row.append(1.0 if diag < thickness else 0.08)
        grid.append(row)
    return grid


def snow(cols: int, rows: int, intensity: float) -> list[list[float]]:
    tier = _rain_tier(intensity)
    density = {1: 0.12, 2: 0.22, 3: 0.35}[tier]
    rng = random.Random()
    return [[1.0 if rng.random() < density else 0.0 for _ in range(cols)] for _ in range(rows)]


def thunderstorm(cols: int, rows: int, intensity: float) -> tuple[list[list[float]], set[tuple[int, int]]]:
    grid = rain(cols, rows, max(intensity, 0.6))
    bolt_col = cols // 2
    accent: set[tuple[int, int]] = set()
    for i, r in enumerate(range(1, rows - 1)):
        col = bolt_col + (1 if i % 2 == 0 else -1)
        if 0 <= col < cols:
            grid[r][col] = 1.0
            accent.add((r, col))
    return grid, accent


def wind(cols: int, rows: int, speed_weight: float) -> list[list[float]]:
    period = max(3, 8 - round(5 * speed_weight))
    length = max(1, round(period * 0.6))
    grid = []
    for r in range(rows):
        phase = (r * 2) % period
        row = []
        for c in range(cols):
            x = (c + phase) % period
            row.append(1.0 if x < length else 0.0)
        grid.append(row)
    return grid


def build(kind: IconKind, intensity: float, cols: int, rows: int) -> tuple[list[list[float]], set[tuple[int, int]]]:
    """Returns (weight_grid, accent_cells) -- accent_cells get ACCENT_CHAR in
    an accent color instead of a vocabulary glyph (currently only the storm
    bolt uses this)."""
    if kind is IconKind.CLEAR:
        return sun(cols, rows, intensity), set()
    if kind is IconKind.PARTLY_CLOUDY:
        sun_grid = sun(cols, rows, 0.6)
        cloud_grid = cloud(cols, rows, 0.5)
        merged = [[max(sun_grid[r][c] * 0.6, cloud_grid[r][c]) for c in range(cols)] for r in range(rows)]
        return merged, set()
    if kind is IconKind.OVERCAST:
        return cloud(cols, rows, max(intensity, 0.7)), set()
    if kind is IconKind.FOG:
        return fog(cols, rows, intensity), set()
    if kind is IconKind.RAIN:
        return rain(cols, rows, intensity), set()
    if kind is IconKind.SNOW:
        return snow(cols, rows, intensity), set()
    if kind is IconKind.THUNDERSTORM:
        return thunderstorm(cols, rows, intensity)
    raise ValueError(f"unhandled icon kind: {kind}")


def compose_wind(
    primary: list[list[float]], wind_grid: list[list[float]], lane_period: int = 3
) -> tuple[list[list[float]], set[tuple[int, int]]]:
    """Carves one row in every `lane_period` into a wind lane that always
    draws from the wind glyph vocabulary (chevrons), regardless of how busy
    the primary condition is there -- a priority rule rather than true alpha
    blending (see the plan's deferred-work note on richer combinations), but
    one that stays visible instead of getting lost under a dense primary
    pattern. Returns (merged_grid, wind_cells); wind_cells tells the caller
    which cells to draw from WIND_VOCAB instead of the primary vocabulary."""
    rows, cols = len(primary), len(primary[0]) if primary else 0
    merged = []
    wind_cells: set[tuple[int, int]] = set()
    for r in range(rows):
        if r % lane_period == 1:
            merged.append(list(wind_grid[r]))
            wind_cells.update((r, c) for c in range(cols))
        else:
            merged.append(list(primary[r]))
    return merged, wind_cells
