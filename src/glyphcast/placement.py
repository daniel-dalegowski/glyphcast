"""Where to put the weather widget on the image: either search for the
calmest spot (reimplementation of Glyphscape's find_quiet_region, operating
directly on pixels instead of a glyph-cell grid -- Glyphcast doesn't have
Glyphscape's cell grid to work with, just a flat PNG), below whatever
centered art is there, or a fixed corner.

"Below art" prefers Glyphscape's own live-geometry.json sidecar (see
geometry.py) for the circle's exact center/radius over pixel-scanning for
it -- exact math beats a luminance-threshold guess, and it's immune to the
sparse-glyph-tail problem pixel-scanning has to work around. The pixel scan
remains as a fallback for when that sidecar is missing or doesn't match
(base_image pointed somewhere else, or an older Glyphscape).

When the configured box doesn't fit in the room below the art, "below art"
scales it down (preserving aspect ratio) to whatever height *is* available
rather than overlapping the art -- a fixed-size fallback corner isn't
reliably clear of the art either, since a wide circle can span most of the
screen's width and height alike. find_box_position's return value reflects
this: (x0, y0, draw_w, draw_h) rather than just a position, so callers know
the size actually to render at."""

from __future__ import annotations

import logging

from PIL import Image, ImageStat

from . import geometry

log = logging.getLogger("glyphcast")

SCAN_STEP = 16  # pixels per scan cell -- coarse is fine, this is just for placement
TOP_MARGIN = 32  # avoid GNOME's top bar
EDGE_MARGIN = 8
BELOW_ART_THRESHOLD = 18.0  # grayscale delta from background that counts as "content"


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _prefix_sums(values: list[list[float]], cols: int, rows: int) -> list[list[float]]:
    prefix = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    for r in range(rows):
        for c in range(cols):
            prefix[r + 1][c + 1] = prefix[r][c + 1] + prefix[r + 1][c] - prefix[r][c] + values[r][c]
    return prefix


def _window_sum(prefix: list[list[float]], top: int, left: int, h: int, w: int) -> float:
    return prefix[top + h][left + w] - prefix[top][left + w] - prefix[top + h][left] + prefix[top][left]


def find_quiet_region(image: Image.Image, box_w: int, box_h: int) -> tuple[int, int]:
    """Returns (x0, y0) pixel origin of the box_w x box_h window of lowest
    luminance variance, avoiding the top bar and the screen's dead center."""
    img_w, img_h = image.size
    small = image.convert("L").resize((max(1, img_w // SCAN_STEP), max(1, img_h // SCAN_STEP)))
    cols, rows = small.size
    px = small.load()
    lum = [[float(px[c, r]) for c in range(cols)] for r in range(rows)]
    lum_sq = [[v * v for v in row] for row in lum]
    sum_prefix = _prefix_sums(lum, cols, rows)
    sq_prefix = _prefix_sums(lum_sq, cols, rows)

    scan_box_w = max(1, box_w // SCAN_STEP)
    scan_box_h = max(1, box_h // SCAN_STEP)
    top_bar_rows = max(1, TOP_MARGIN // SCAN_STEP)
    edge = max(1, EDGE_MARGIN // SCAN_STEP)

    center_top, center_bottom = int(rows * 0.3), int(rows * 0.7)
    center_left, center_right = int(cols * 0.3), int(cols * 0.7)

    best, best_variance = None, float("inf")
    n = scan_box_w * scan_box_h
    for top in range(top_bar_rows, max(top_bar_rows + 1, rows - scan_box_h - edge)):
        for left in range(edge, max(edge + 1, cols - scan_box_w - edge)):
            bottom, right = top + scan_box_h, left + scan_box_w
            if top < center_bottom and bottom > center_top and left < center_right and right > center_left:
                continue
            s = _window_sum(sum_prefix, top, left, scan_box_h, scan_box_w)
            sq = _window_sum(sq_prefix, top, left, scan_box_h, scan_box_w)
            mean = s / n
            variance = sq / n - mean * mean
            if variance < best_variance:
                best_variance, best = variance, (top, left)

    if best is None:
        x0 = (img_w - box_w) // 2
        y0 = img_h - box_h - EDGE_MARGIN
        return max(0, x0), max(0, y0)

    top, left = best
    return left * SCAN_STEP, top * SCAN_STEP


def corner_position(image: Image.Image, box_w: int, box_h: int, corner: str, margin: int) -> tuple[int, int]:
    img_w, img_h = image.size
    x0 = margin if "left" in corner else img_w - box_w - margin
    y0 = margin if "top" in corner else img_h - box_h - margin
    if "top" in corner:
        y0 = max(y0, TOP_MARGIN)
    return max(0, x0), max(0, y0)


def _background_color(image: Image.Image, patch: int = 10) -> tuple[int, int, int]:
    """Average of the four corners -- reliable for Glyphscape's output since
    everything outside its circle is a single flat fill color, but works for
    any image with a plain border too."""
    w, h = image.size
    patch = min(patch, w, h)
    corners = [
        image.crop((0, 0, patch, patch)),
        image.crop((w - patch, 0, w, patch)),
        image.crop((0, h - patch, patch, h)),
        image.crop((w - patch, h - patch, w, h)),
    ]
    sums = [0.0, 0.0, 0.0]
    for c in corners:
        mean = ImageStat.Stat(c.convert("RGB")).mean
        for i in range(3):
            sums[i] += mean[i]
    return tuple(round(s / len(corners)) for s in sums)


def _content_bottom_px(image: Image.Image) -> float:
    """Lowest row (within a horizontally-centered band) that still differs
    from the background color -- i.e. the bottom edge of whatever centered
    content (Glyphscape's circle medallion, or any other centered art) sits
    in the upper/middle part of the image.

    Scans full-resolution pixels rather than a downsampled thumbnail.
    Glyphscape's art thins out to individually sparse, scattered glyphs
    near the circle's edge rather than stopping cleanly -- resizing the
    image down first (as an earlier version of this did) averages each
    block of source pixels together, which dilutes a lone bright glyph
    surrounded by background below the detection threshold. That silently
    under-measured the art's true extent by over 100px on a real render,
    letting the box land close enough to the sparse tail to look like it
    was cutting the circle off."""
    img_w, img_h = image.size
    bg = _background_color(image)
    bg_gray = sum(bg) / 3

    gray = image.convert("L")
    px = gray.load()
    band_x0, band_x1 = int(img_w * 0.2), int(img_w * 0.8)

    content_bottom_px = 0
    for y in range(img_h):
        for x in range(band_x0, band_x1):
            if abs(px[x, y] - bg_gray) > BELOW_ART_THRESHOLD:
                content_bottom_px = y
                break
    return float(content_bottom_px)


def _content_bottom_and_center(image: Image.Image, base_image_path) -> tuple[float, float]:
    """(content_bottom_y, center_x) -- from Glyphscape's geometry sidecar
    when it's present and matches this image, else a pixel scan for
    content_bottom_y paired with the image's horizontal center (pixel-
    scanning only ever looked for centered content to begin with)."""
    geo = geometry.load(base_image_path, image.size) if base_image_path else None
    if geo is not None and geo.circle_bottom is not None:
        return geo.circle_bottom, geo.circle_center[0]
    return _content_bottom_px(image), image.size[0] / 2


def find_below_art(
    image: Image.Image, box_w: int, box_h: int, margin: int, base_image_path=None
) -> tuple[int, int, int, int] | None:
    """Centers a box under whatever centered art is in the image (the
    circle, per Glyphscape's geometry sidecar, or pixel-scanned content),
    just below it. Downscales the box (preserving aspect ratio) to whatever
    height is actually available between the art's bottom edge and the
    image's bottom edge when the configured size doesn't fit -- instead of
    overlapping the art, which a fixed-size corner fallback can't reliably
    avoid either (a wide circle can span most of the screen's width and
    height alike, so even a corner box can land on top of it).

    Returns (x0, y0, draw_w, draw_h); None if there's no usable room at all
    (the art already runs to within `margin` of the image's bottom edge)."""
    img_w, img_h = image.size
    content_bottom, center_x = _content_bottom_and_center(image, base_image_path)

    available_h = img_h - content_bottom - margin
    if available_h <= 0:
        log.warning(
            "no room below the art for the forecast box at all (content bottom at y=%.0f, "
            "margin %d, image height %d) -- leaving it off this render",
            content_bottom, margin, img_h,
        )
        return None

    scale = min(1.0, available_h / box_h)
    draw_w, draw_h = max(1, round(box_w * scale)), max(1, round(box_h * scale))
    if scale < 1.0:
        log.info(
            "only %.0fpx below the art for a %dx%d box -- scaling to %dx%d to fit",
            available_h, box_w, box_h, draw_w, draw_h,
        )

    x0 = round(center_x - draw_w / 2)
    x0 = max(0, min(x0, img_w - draw_w))
    y0 = round(content_bottom + margin)
    return x0, y0, draw_w, draw_h


def find_box_position(
    image: Image.Image,
    box_w: int,
    box_h: int,
    mode: str,
    corner: str,
    margin: int,
    base_image_path=None,
) -> tuple[int, int, int, int] | None:
    if mode == "off":
        return None
    if mode == "corner":
        x0, y0 = corner_position(image, box_w, box_h, corner, margin)
        return x0, y0, box_w, box_h
    if mode == "below-art":
        return find_below_art(image, box_w, box_h, margin, base_image_path)
    x0, y0 = find_quiet_region(image, box_w, box_h)
    return x0, y0, box_w, box_h
