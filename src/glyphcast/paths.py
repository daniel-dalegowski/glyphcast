"""XDG-ish paths used throughout the pipeline."""

from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", str(home() / ".config"))
    return Path(base) / "glyphcast"


def config_file() -> Path:
    return config_dir() / "config.toml"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", str(home() / ".cache"))
    return Path(base) / "glyphcast"


def variant_cache_dir(dark: bool) -> Path:
    return cache_dir() / ("dark" if dark else "light")


def pristine_png(dark: bool) -> Path:
    return variant_cache_dir(dark) / "pristine.png"


def output_hash_file(dark: bool) -> Path:
    return variant_cache_dir(dark) / "output.sha256"
