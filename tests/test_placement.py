import json

from PIL import Image, ImageDraw

from glyphcast.placement import find_below_art, find_box_position


def test_find_below_art_sits_under_a_centered_circle_at_full_size():
    w, h = 1600, 1000
    img = Image.new("RGB", (w, h), (5, 5, 5))
    draw = ImageDraw.Draw(img)
    cx, cy, r = w / 2, h * 0.45, 300
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(120, 140, 110))

    box_w, box_h = 900, 150
    x0, y0, draw_w, draw_h = find_below_art(img, box_w, box_h, margin=20)

    circle_bottom = cy + r
    # plenty of room below this circle -- no scaling needed
    assert (draw_w, draw_h) == (box_w, box_h)
    # centered horizontally
    assert abs(x0 - (w - box_w) / 2) < 5
    # placed at/below the circle's true bottom edge, with slack for the
    # coarse downsampled scan
    assert y0 >= circle_bottom - 30
    # and not needlessly far below it either
    assert y0 <= circle_bottom + 60


def test_find_below_art_scales_down_to_fit_when_content_runs_low():
    """When the art extends too close to the bottom edge for the full-size
    box to fit below it, the box must shrink (preserving aspect ratio) to
    whatever room is actually available -- not overlap the art, and not
    jump to a fixed corner either (a wide circle can span most of the
    screen's width and height alike, so a corner box isn't reliably clear
    of it)."""
    w, h = 800, 400
    img = Image.new("RGB", (w, h), (5, 5, 5))
    draw = ImageDraw.Draw(img)
    content_bottom = 340
    draw.rectangle([100, 0, 700, content_bottom], fill=(200, 200, 200))

    box_w, box_h = 700, 150  # would need to reach y=170+150=320.. plus margin pushes past h
    margin = 40
    x0, y0, draw_w, draw_h = find_below_art(img, box_w, box_h, margin=margin)

    available_h = h - content_bottom - margin
    assert draw_h == available_h
    assert draw_w == round(box_w * (available_h / box_h))
    # fits exactly within the image, flush with the bottom edge
    assert y0 + draw_h == h
    # stays centered horizontally
    assert abs(x0 - (w - draw_w) / 2) < 5


def test_find_below_art_returns_none_when_there_is_no_room_at_all():
    w, h = 800, 400
    img = Image.new("RGB", (w, h), (5, 5, 5))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, h - 5], fill=(200, 200, 200))  # content runs to 5px from the bottom

    assert find_below_art(img, 700, 150, margin=20) is None


def _write_geometry(path, resolution, center, radius, enabled=True):
    path.write_text(json.dumps({
        "resolution": list(resolution),
        "background_rgb": [5, 5, 5],
        "circle": {"enabled": enabled, "center": list(center), "radius": radius, "feather": 0.0},
        "config": {},
    }))


def test_find_box_position_uses_geometry_sidecar_when_present(tmp_path):
    w, h = 1600, 1000
    img = Image.new("RGB", (w, h), (5, 5, 5))
    cx, cy, r = 850.0, 450.0, 300.0  # off-center, to prove it tracks the circle, not image width/2
    _write_geometry(tmp_path / "live-geometry.json", (w, h), (cx, cy), r)
    base_image_path = tmp_path / "live.png"

    box_w, box_h = 900, 150
    x0, y0, draw_w, draw_h = find_box_position(img, box_w, box_h, "below-art", "bottom-right", 20, base_image_path)

    circle_bottom = cy + r
    assert (draw_w, draw_h) == (box_w, box_h)
    assert (x0, y0) == (round(cx - box_w / 2), round(circle_bottom + 20))


def test_find_box_position_scales_down_when_geometry_leaves_insufficient_room(tmp_path):
    w, h = 1600, 1000
    img = Image.new("RGB", (w, h), (5, 5, 5))
    cx, cy, r = 850.0, 620.0, 300.0  # circle bottom at 920 -- only 60px of the 150px needed
    _write_geometry(tmp_path / "live-geometry.json", (w, h), (cx, cy), r)
    base_image_path = tmp_path / "live.png"

    box_w, box_h, margin = 900, 150, 20
    pos = find_box_position(img, box_w, box_h, "below-art", "bottom-right", margin, base_image_path)

    circle_bottom = cy + r
    available_h = h - circle_bottom - margin
    assert pos == (
        round(cx - round(box_w * (available_h / box_h)) / 2),
        round(circle_bottom + margin),
        round(box_w * (available_h / box_h)),
        round(available_h),
    )


def test_find_box_position_returns_none_when_geometry_leaves_no_room(tmp_path):
    w, h = 1600, 1000
    img = Image.new("RGB", (w, h), (5, 5, 5))
    cx, cy, r = 850.0, 975.0, 300.0  # circle bottom at 1275 -- well past the image's bottom edge
    _write_geometry(tmp_path / "live-geometry.json", (w, h), (cx, cy), r)
    base_image_path = tmp_path / "live.png"

    pos = find_box_position(img, 900, 150, "below-art", "bottom-right", 20, base_image_path)
    assert pos is None
