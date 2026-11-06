"""Where to put the weather widget on the image: either search for the
calmest spot (reimplementation of Glyphscape's find_quiet_region, operating
directly on pixels instead of a glyph-cell grid -- Glyphcast doesn't have
Glyphscape's cell grid to work with, just a flat PNG) or a fixed corner."""

from __future__ import annotations

from PIL import Image, ImageStat

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


def find_below_art(image: Image.Image, box_w: int, box_h: int, margin: int) -> tuple[int, int]:
    """Finds the lowest row (within a horizontally-centered band) that still
    differs from the background color, and centers the box just below it --
    i.e. below whatever centered content (Glyphscape's circle medallion, or
    any other centered art) sits in the upper/middle part of the image.

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

    x0 = max(0, (img_w - box_w) // 2)
    y0 = content_bottom_px + margin
    # Only pull the box up if it would otherwise run off the bottom of the
    # image -- not as a matter of course. The old formula subtracted an
    # extra margin//2 unconditionally, which could pull the box back up
    # into the content it's supposed to sit below even when there was
    # plenty of room to spare.
    y0 = min(y0, max(0, img_h - box_h))
    return x0, y0


def find_box_position(image: Image.Image, box_w: int, box_h: int, mode: str, corner: str, margin: int) -> tuple[int, int] | None:
    if mode == "off":
        return None
    if mode == "corner":
        return corner_position(image, box_w, box_h, corner, margin)
    if mode == "below-art":
        return find_below_art(image, box_w, box_h, margin)
    return find_quiet_region(image, box_w, box_h)
