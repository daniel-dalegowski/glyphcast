from PIL import Image, ImageDraw

from glyphcast.placement import find_below_art


def test_find_below_art_sits_under_a_centered_circle():
    w, h = 1600, 1000
    img = Image.new("RGB", (w, h), (5, 5, 5))
    draw = ImageDraw.Draw(img)
    cx, cy, r = w / 2, h * 0.45, 300
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(120, 140, 110))

    box_w, box_h = 900, 150
    x0, y0 = find_below_art(img, box_w, box_h, margin=20)

    circle_bottom = cy + r
    # centered horizontally
    assert abs(x0 - (w - box_w) / 2) < 5
    # placed at/below the circle's true bottom edge, with slack for the
    # coarse downsampled scan
    assert y0 >= circle_bottom - 30
    # and not needlessly far below it either
    assert y0 <= circle_bottom + 60


def test_find_below_art_clamps_to_image_when_content_runs_low():
    w, h = 800, 400
    img = Image.new("RGB", (w, h), (5, 5, 5))
    draw = ImageDraw.Draw(img)
    draw.ellipse([w / 2 - 350, h - 400, w / 2 + 350, h + 100], fill=(200, 200, 200))

    box_w, box_h = 700, 150
    x0, y0 = find_below_art(img, box_w, box_h, margin=20)

    assert y0 + box_h <= h
    assert x0 >= 0
