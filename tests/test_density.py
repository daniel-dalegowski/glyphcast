"""The small-icon-size regression: build_bins used to measure glyph ink on a
fixed 48px canvas regardless of the font's actual point size, which diluted
small glyphs' scores below the blank-filter cutoff and silently collapsed
whole vocabularies (rain, snow, fog, wind) down to just the blank
character at icon_cell sizes below ~10px. See the fix's comment in
density.py."""

import subprocess
import shutil

import pytest
from PIL import ImageFont

from glyphcast import density

RAIN_VOCAB = " .'|╲"


def _dejavu_sans_path() -> str:
    if not shutil.which("fc-match"):
        pytest.skip("fc-match not available")
    return subprocess.run(
        ["fc-match", "-f", "%{file}", "DejaVu Sans"], capture_output=True, text=True, timeout=5
    ).stdout


def test_small_icon_font_still_yields_multiple_usable_glyphs():
    font_path = _dejavu_sans_path()
    font = ImageFont.truetype(font_path, 7)  # Glyphcast's smaller default icon_cell
    bins = density.build_bins(RAIN_VOCAB, font, num_bins=6)

    non_blank = {ch for b in bins for ch in b if ch != " "}
    assert len(non_blank) >= 2, f"expected multiple surviving rain glyphs at size 7, got {non_blank!r}"


def test_pick_at_full_weight_is_not_always_blank():
    font_path = _dejavu_sans_path()
    font = ImageFont.truetype(font_path, 7)
    bins = density.build_bins(RAIN_VOCAB, font, num_bins=6)

    import random
    rng = random.Random(0)
    picks = {density.pick(bins, 1.0, rng) for _ in range(20)}
    assert picks != {" "}
