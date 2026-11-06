# Glyphcast

An hourly weather overlay, composited onto a static image -- by default, Glyphscape's own GNOME wallpaper -- in the same density-ramp glyph language Glyphscape renders its art with: a sun as a radial burst of glyphs that fall off toward the edges, rain as diagonal streaks whose density scales with intensity, fog as a soft scattered field, wind as chevrons that cut lanes through whatever else is drawn. Day labels and hi/lo temps are deliberately plain by contrast: solid-color text, for legibility. By default it renders a 7-day forecast strip, centered horizontally and placed just below whatever centered content (Glyphscape's circle medallion, typically) sits in the image -- a single-day "current conditions" widget (`layout = "current"`) is also available.

Glyphcast is a separate project from Glyphscape on purpose. Glyphscape renders once a day with a seed-deterministic art pipeline; weather needs to refresh roughly hourly. Rather than bolt a fast-changing data feed onto a slow art pipeline, Glyphcast owns fetching weather and compositing it onto whatever image you point it at -- Glyphscape stays untouched, and Glyphcast doesn't depend on it as a library.

## How it avoids stomping on itself

The common setup points `output` at the same file as `base_image` -- Glyphcast writes weather back onto Glyphscape's own `live.png`. Run naively, "read image, stamp weather, write it back" every hour would stamp weather on top of its own last stamp, forever. Glyphcast avoids this with a small hash-cached pristine-base mechanism (`compositor.resolve_pristine`): each run, it hashes the current bytes at `base_image`; if that hash matches what Glyphcast itself wrote to `output` last time, nothing else has touched the file, so it recomposites from a cached pristine copy instead of the file it just wrote. If the hash differs -- Glyphscape just published a fresh day's art, or `base_image` changed some other way -- that's treated as the new pristine frame. This makes `base_image == output` and `base_image != output` both just work, with zero changes needed to whatever produced the base image.

## Visual language (v1)

Each condition is a small procedural weight grid (radial falloff for sun, overlapping blobs for cloud, diagonal streaks for rain, scattered dots for snow, flowing chevrons for wind) that picks glyphs from a density-binned vocabulary -- the same algorithmic idea as Glyphscape's own glyph selection (local "intensity" picks a density bin, which picks a glyph), reimplemented standalone in `density.py` since the vocabulary here is weather-specific and tiny, not worth a runtime dependency on Glyphscape. Rain and snow have three visible intensity tiers. Wind overlays as horizontal chevron lanes cut through whatever the primary condition drew, rather than competing for the same cells and sometimes vanishing. A thunderstorm draws a rain field plus an accent-colored lightning zigzag.

The glyph-ink measurement that drives density binning scales its canvas to the font's own point size rather than a fixed size -- without that, shrinking `icon_cell` down toward single-digit pixel sizes silently collapsed whole vocabularies (rain, snow, fog, wind -- anything built from thin strokes rather than filled dots/blocks) down to just the blank character, since a tiny glyph only fills a small corner of a fixed-size measurement canvas. `tests/test_density.py` pins this down.

This is a first design pass, meant to be looked at and iterated on -- `glyphcast render --mock <condition>` renders any single condition against a backdrop you provide without touching the network, and `glyphcast render --forecast` does the same for a synthetic 7-day strip.

**Deferred past v1**: true alpha-blended combinations beyond the wind-lane priority rule (e.g. a sun partially occluded by a moving cloud shape), and any seasonal/time-of-day variation in the glyph palette.

## Installation (NixOS / home-manager)

```nix
# your flake.nix
{
  inputs.glyphcast.url = "github:daniel-dalegowski/glyphcast";

  outputs = { home-manager, glyphcast, ... }: {
    homeConfigurations.you = home-manager.lib.homeManagerConfiguration {
      modules = [
        glyphcast.homeManagerModules.default
        {
          programs.glyphcast = {
            enable = true;
            settings = {
              latitude = 47.6062;
              longitude = -122.3321;
            };
          };
        }
      ];
    };
  };
}
```

This installs the `glyphcast` CLI, writes `~/.config/glyphcast/config.toml`, and sets up a `systemd --user` timer (`glyphcast.timer`, hourly by default, catches up after sleep). It does not register a GNOME wallpaper entry itself -- by default it writes into Glyphscape's already-registered `live.png`/`live-dark.png`.

### Without a flake

`nix/module.nix` is a plain home-manager module and doesn't need a flake input -- import it by path the same way as Glyphscape's (see Glyphscape's own README for the channel-based pattern).

## Manual commands

```
glyphcast                                          # fetch + composite, using the configured location
glyphcast now                                       # same -- there's no daily "already done" skip to force past
glyphcast render --forecast --base photo.png         # render a synthetic 7-day strip, no network
glyphcast render --mock rain3 --base photo.png        # render one condition (current-style widget), no network
glyphcast render --mock rain3 --base photo.png --out preview.png --publish
```

Mock conditions: `clear`, `partly-cloudy`, `overcast`, `fog`, `rain1`, `rain2`, `rain3`, `snow`, `storm`, `windy`.

## Configuration

`~/.config/glyphcast/config.toml`, generated from `programs.glyphcast.settings` on NixOS, or hand-edited otherwise.

| Key | Default | Meaning |
|---|---|---|
| `latitude` / `longitude` | `0.0` | Forecast location. Required -- look these up once; Glyphcast doesn't geocode a city name in v1. |
| `units` | `"metric"` | `"metric"` or `"imperial"` -- drives temperature (°C/°F), wind speed (km/h/mph), and precipitation (mm/inch) together, not separately |
| `base_image` | Glyphscape's `live.png` | Backdrop to composite onto |
| `base_image_dark` | Glyphscape's `live-dark.png` | Dark-variant backdrop; `""` disables the dark variant entirely |
| `output` / `output_dark` | same as the `base_image` keys | Where the composited result is written |
| `layout` | `"forecast"` | `"forecast"` (N-day strip) or `"current"` (today only, one larger widget) |
| `forecast_days` | `7` | Number of days in the strip, when `layout = "forecast"` |
| `style` | `"glyph"` | `"glyph"` (full density-ramp icon language) or `"plain"` (a single stock symbol, cheap fallback/testing mode) |
| `box` | `"980x170"` | Overall widget size in pixels, `"WxH"` |
| `icon_cell` | `"7x7"` | Pixel size of one icon glyph cell |
| `font` | `"DejaVu Sans"` | Font for both the icon glyphs and the text |
| `text_font_size` | `22` | Point size for the hi/lo temperature |
| `label_font_size` | `15` | Point size for the day label |
| `wind_overlay_threshold` | `25` | Wind *gust* speed (km/h if `units=metric`, mph if `imperial`) above which wind chevrons overlay any condition -- gusts, not sustained speed, since a gusty day reads as "windy" even when the sustained speed alone wouldn't cross the threshold |
| `placement.mode` | `"below-art"` | `"below-art"` (centered under whatever centered content sits in the image), `"quiet-region"` (search for the calmest spot), `"corner"`, or `"off"` |
| `placement.corner` | `"bottom-right"` | Used when `placement.mode = "corner"` |
| `placement.margin` | `56` | Pixel margin below the detected content (`below-art`) or from the edge (`corner`) |

### What drives condition/intensity

Each day (or the current nowcast, in `layout = "current"`) pulls more than just the WMO weather code: rain and snowfall are fetched as separate totals (`rain_sum`/`showers_sum` vs `snowfall_sum`, not one blended `precipitation_sum`), so a rain day and a snow day each scale their own icon intensity off the right number instead of a shared one that doesn't distinguish them. `precipitation_probability_max` is fetched but not yet drawn anywhere -- it's there for a future confidence indicator.

On days with measurable precipitation, the projected amount (whichever matches the day's classified condition -- rain+showers, or snowfall) is drawn below the hi/lo temp as a droplet + number, e.g. a teardrop followed by "6mm". Days with no precipitation leave that row blank. The droplet is drawn directly (`compositor._draw_droplet`, a small polygon-and-circle shape), not pulled from a font glyph -- DejaVu Sans doesn't actually contain the Unicode water-drop emoji (U+1F4A7) and silently renders it as a blank box, and none of the characters that *do* render (triangles, umbrellas) read as "droplet" at a glance. Several candidates were visually spot-checked before settling on drawing the shape by hand instead of gambling on font coverage again.

## Development / testing without Nix

```
pip install -e .
export XDG_CONFIG_HOME=~/.config-test
export XDG_CACHE_HOME=~/.cache-test
export XDG_DATA_HOME=~/.local/share-test
glyphcast render --mock storm --base some-photo.png   # writes ./glyphcast-preview-storm.png
```

Needs fontconfig and a monospace-ish font with decent symbol coverage visible to it (`fc-match "DejaVu Sans"` should resolve) -- on Debian/Ubuntu: `apt install fonts-dejavu-core`. On NixOS without a global Pillow/requests install, `nix-shell -p 'python3.withPackages(ps: [ps.pillow ps.requests])' fontconfig dejavu_fonts` works well for ad hoc testing -- pip-installed Pillow wheels can fail on NixOS with a missing `libz.so.1` since they're built against FHS paths NixOS doesn't provide.
