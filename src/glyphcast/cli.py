"""Entry point: `glyphcast [now|render --mock <condition>]`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config as config_mod, pipeline, publish
from .pipeline import MOCKS

log = logging.getLogger("glyphcast")


def _parse_bool(raw: str) -> bool:
    if raw.lower() in ("true", "1", "yes", "on"):
        return True
    if raw.lower() in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"not a boolean: {raw!r}")


def _apply_overrides(config, overrides: list[str]) -> None:
    settable = config_mod.settable_keys()
    for item in overrides:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got {item!r}")
        key, raw_value = (part.strip() for part in item.split("=", 1))
        attr = settable.get(key)
        if attr is None:
            raise SystemExit(f"unknown config key for --set: {key!r}")
        current = getattr(config, attr)
        try:
            if isinstance(current, bool):
                value = _parse_bool(raw_value)
            elif isinstance(current, int):
                value = int(raw_value)
            elif isinstance(current, float):
                value = float(raw_value)
            else:
                value = raw_value
        except ValueError as exc:
            raise SystemExit(f"--set {key}: {exc}") from exc
        setattr(config, attr, value)


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _cmd_run(config, force: bool) -> int:
    ok = pipeline.run(config, force=force)
    return 0 if ok else 1


def _cmd_render(args, config) -> int:
    base_path = Path(args.base).expanduser() if args.base else None
    if base_path is None:
        log.error("--base <image> is required for render")
        return 1
    if not base_path.is_file():
        log.error("no such file: %s", base_path)
        return 1
    if not args.forecast and not args.mock:
        log.error("render needs either --mock <condition> or --forecast")
        return 1

    try:
        if args.forecast:
            data = pipeline.render_mock_forecast(config, base_path)
            name = "forecast"
        else:
            data = pipeline.render_mock(args.mock, config, base_path)
            name = args.mock
    except ValueError as exc:
        log.error(str(exc))
        return 1

    out = Path(args.out) if args.out else Path.cwd() / f"glyphcast-preview-{name}.png"
    publish.atomic_write_bytes(data, out)
    log.info("wrote %s", out)

    if args.publish:
        publish.atomic_write_bytes(data, Path(config.output).expanduser())
        log.info("published to %s", config.output)
    return 0


def main(argv=None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(prog="glyphcast")
    parser.add_argument(
        "--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE",
        help="override a config value, e.g. --set style=plain (repeatable)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("now", help="force a fresh fetch and render")

    render_parser = sub.add_parser("render", help="render without fetching, for testing/tuning")
    render_parser.add_argument("--mock", choices=sorted(MOCKS), help="single condition to render (current-style widget)")
    render_parser.add_argument("--forecast", action="store_true", help="render a synthetic 7-day forecast strip instead")
    render_parser.add_argument("--base", required=True, help="backdrop image to composite onto")
    render_parser.add_argument("--out", help="output PNG path (default ./glyphcast-preview-<mock>.png)")
    render_parser.add_argument("--publish", action="store_true", help="also write to the configured output path")

    args = parser.parse_args(argv)
    config = config_mod.load()
    if args.overrides:
        _apply_overrides(config, args.overrides)

    if args.command == "now":
        return _cmd_run(config, force=True)
    if args.command == "render":
        return _cmd_render(args, config)

    return _cmd_run(config, force=False)


if __name__ == "__main__":
    sys.exit(main())
