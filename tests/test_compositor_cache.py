"""The hash-cached pristine-base mechanism is the part of this project most
likely to have a subtle bug (see the plan's "Solving accumulation" section)
-- these pin down both scenarios it has to handle: base_image == output
(the normal case, writing weather back onto Glyphscape's own live.png) and
an external rewrite of base_image showing up as a fresh frame."""

from PIL import Image

from glyphcast import compositor


def _make_image(path, color):
    Image.new("RGB", (10, 10), color).save(path)


def test_pristine_cache_stable_across_repeated_same_path_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    base = tmp_path / "live.png"
    _make_image(base, (10, 20, 30))

    img1 = compositor.resolve_pristine(base, dark=False)
    data1 = b"stand-in composited output bytes"
    compositor.record_output_hash(data1, dark=False)
    base.write_bytes(data1)  # glyphcast writing its own result back over the same path

    img2 = compositor.resolve_pristine(base, dark=False)
    assert list(img2.getdata()) == list(img1.getdata())


def test_pristine_cache_detects_external_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    base = tmp_path / "live.png"
    _make_image(base, (10, 20, 30))

    img1 = compositor.resolve_pristine(base, dark=False)
    compositor.record_output_hash(b"our last output", dark=False)
    base.write_bytes(b"our last output")

    # something else (Glyphscape) rewrites base_image with a brand new frame
    _make_image(base, (99, 88, 77))
    img2 = compositor.resolve_pristine(base, dark=False)

    assert list(img2.getdata())[0] == (99, 88, 77)
    assert list(img2.getdata()) != list(img1.getdata())


def test_pristine_cache_first_run_has_no_prior_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    base = tmp_path / "live.png"
    _make_image(base, (1, 2, 3))

    img = compositor.resolve_pristine(base, dark=False)
    assert list(img.getdata())[0] == (1, 2, 3)
