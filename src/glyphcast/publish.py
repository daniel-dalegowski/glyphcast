"""Atomic file publishing: write a temp file, then atomically rename over
the destination, so nothing (GNOME's wallpaper watcher, Glyphscape's next
run) ever sees a partial write."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_bytes(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dest.parent, suffix=".png.tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_path, dest)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
