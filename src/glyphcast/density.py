"""Generic density-ramp glyph picking: given a small curated character
vocabulary and a font, measure how much "ink" each glyph has, bin by that,
and pick weighted-random glyphs from a bin with recent-repeat suppression.

Same algorithmic idea as Glyphscape's glyphsets.py (a photo's local texture
picks a density bin, which picks a glyph) -- reimplemented standalone here
since the vocabulary is weather-specific and tiny, not worth a dependency on
Glyphscape itself."""

from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFont


def glyph_ink(font: ImageFont.FreeTypeFont, char: str, size: int = 48) -> float:
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    draw.text((size / 2, size / 2), char, font=font, fill=255, anchor="mm")
    pixels = img.tobytes()
    return sum(pixels) / len(pixels)


def build_bins(chars: str, font: ImageFont.FreeTypeFont, num_bins: int = 6) -> list[list[str]]:
    """Order `chars` (a string, blank-first by convention) by measured ink
    and bucket into `num_bins` groups, lowest-ink first. Characters the font
    renders as blank (ink <= 1, i.e. a true space) are dropped rather than
    risking a silent tofu box skewing the ramp.

    The measurement canvas scales with the font's own point size: a glyph
    drawn at a small icon_cell (this project shrinks icon glyphs down to
    single-digit pixel sizes) only fills a small corner of a fixed-size
    canvas, which dilutes its measured ink arbitrarily -- at a 7px font on
    the old fixed 48px canvas, every stroke-based character in a vocabulary
    like rain's measured under the cutoff and got silently dropped, leaving
    only blank space to pick from. Scaling the canvas to the font size keeps
    the measurement (and therefore the cutoff) meaningful at any size."""
    measure_size = max(16, round(font.size * 3))
    scored = [(glyph_ink(font, ch, size=measure_size), ch) for ch in chars]
    scored = [(d, ch) for d, ch in scored if ch == " " or d > 1]
    if not scored:
        raise RuntimeError("no usable glyphs in vocabulary")

    scored.sort(key=lambda pair: pair[0])
    densities = [d for d, _ in scored]
    dmin, dmax = densities[0], densities[-1]
    span = (dmax - dmin) or 1.0

    bins: list[list[str]] = [[] for _ in range(num_bins)]
    for d, ch in scored:
        idx = min(num_bins - 1, int((d - dmin) / span * num_bins))
        bins[idx].append(ch)
    return bins


def _nearest_nonempty(bins: list[list[str]], idx: int) -> int:
    if bins[idx]:
        return idx
    for radius in range(1, len(bins)):
        for cand in (idx - radius, idx + radius):
            if 0 <= cand < len(bins) and bins[cand]:
                return cand
    return idx


def pick(
    bins: list[list[str]],
    weight: float,
    rng: random.Random,
    avoid: set[str] | None = None,
    max_tries: int = 5,
) -> str:
    """weight: 0 (blank/sparsest) .. 1 (densest)."""
    idx = min(len(bins) - 1, max(0, int(weight * len(bins))))
    idx = _nearest_nonempty(bins, idx)
    candidates = bins[idx]
    if not avoid:
        return rng.choice(candidates)
    best = candidates[0]
    for _ in range(max_tries):
        ch = rng.choice(candidates)
        if ch not in avoid:
            return ch
        best = ch
    return best
