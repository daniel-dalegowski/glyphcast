"""Reads Glyphscape's live-geometry.json sidecar, if there is one next to
the base image, so placement can use the circle's exact center/radius
instead of re-deriving it by scanning pixels for a luminance threshold.

Comprehensive by design (the sidecar also carries the resolved background
color and Glyphscape's full config) since it's meant as a general-purpose
"how was this wallpaper rendered" record for any tool that composites onto
it, not just this one placement decision."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("glyphcast")

SIDECAR_NAME = "live-geometry.json"


@dataclass
class Geometry:
    resolution: tuple[int, int]
    background_rgb: tuple[int, int, int] | None
    circle_enabled: bool
    circle_center: tuple[float, float] | None
    circle_radius: float | None

    @property
    def circle_bottom(self) -> float | None:
        if not self.circle_enabled or self.circle_center is None or self.circle_radius is None:
            return None
        return self.circle_center[1] + self.circle_radius


def load(base_image_path: Path, image_size: tuple[int, int]) -> Geometry | None:
    """None if there's no sidecar, it's unreadable, or its recorded
    resolution doesn't match the image actually being composited onto --
    e.g. base_image points somewhere that isn't a Glyphscape render, or the
    sidecar is stale relative to a base image someone else just replaced."""
    sidecar = base_image_path.parent / SIDECAR_NAME
    if not sidecar.is_file():
        return None
    try:
        data = json.loads(sidecar.read_text())
        resolution = tuple(data["resolution"])
        if resolution != tuple(image_size):
            log.info(
                "ignoring %s: recorded resolution %s doesn't match base image %s",
                sidecar, resolution, image_size,
            )
            return None
        circle = data.get("circle") or {}
        bg = data.get("background_rgb")
        center = circle.get("center")
        radius = circle.get("radius")
        return Geometry(
            resolution=resolution,
            background_rgb=tuple(bg) if bg else None,
            circle_enabled=bool(circle.get("enabled", False)),
            circle_center=tuple(center) if center else None,
            circle_radius=float(radius) if radius is not None else None,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("couldn't read %s: %s", sidecar, exc)
        return None
