# Lunar Orbiter Atlas

[![CI](https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS/actions/workflows/ci.yml/badge.svg)](https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS/actions/workflows/ci.yml)
[![Pages](https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS/actions/workflows/pages.yml/badge.svg)](https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS/actions/workflows/pages.yml)
[![Project page](https://img.shields.io/badge/project%20page-GitHub%20Pages-ff7547)](https://enriqueph.github.io/LUNAR-ORBITER-ATLAS/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](pyproject.toml)
[![Dash](https://img.shields.io/badge/built%20with-Dash%20%2B%20Plotly-3f4f75)](https://dash.plotly.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A local web app for exploring the photographs of NASA's Lunar Orbiter missions
(1966–1967) on an interactive 3D Moon. Images and metadata come from the
[Lunar and Planetary Institute (LPI) Lunar Orbiter Photo Gallery](https://www.lpi.usra.edu/resources/lunarorbiter/).

<img src="orbiter/assets/icon.png" alt="" width="96" align="right">

Repository: <https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS> ·
Project page: <https://enriqueph.github.io/LUNAR-ORBITER-ATLAS/>

## Features

- **Mission mosaic** — every frame of the selected mission is projected onto
  the part of the Moon it photographed. Click a photo to show its details in
  the side panel.
- **Frame details** — LPI preview, principal point, spacecraft altitude and
  position, and illumination angles (sun azimuth, incidence, emission, phase).
- **Reference tabs** — summarised facts about the Moon and the Lunar Orbiter
  program, with their Wikipedia sources.
- **English and Spanish** — switch with the **ES | EN** control in the top bar
  (or open `?lang=en` / `?lang=es`).
- Equator and north/south poles are marked on the globe; frames taken above
  1000 km are outlined and flagged in the side panel.

### How photos are placed

Each frame is projected from the spacecraft: every pixel becomes a ray from
the spacecraft position published by the LPI, through the camera, aimed at the
principal point, and lands where that ray meets the Moon. Oblique and
high-altitude shots therefore cover the area they really saw, and pixels that
look past the limb are dropped.

- **Camera.** The thumbnail shows the medium-resolution frame (80 mm lens,
  55 × 65 mm) when the gallery has one, otherwise the middle third of the
  high-resolution frame (610 mm lens). From 46 km the model covers
  31.7 × 37.5 km, matching the documented 31.6 × 37.4 km.
- **Check.** For 890 frames the emission angle implied by the spacecraft
  position matches the LPI's (median error 0.06°). The 22 frames whose metadata
  disagree by more than 5° fall back to a simple north-up patch.
- **Orientation.** The image's rotation is not published. Near-vertical frames
  are drawn north-up and oblique ones level with the horizon at the top, as the
  gallery shows them. High-altitude frames that see the limb are turned so their
  off-Moon pixels land on the black sky in the image.
- **Limits.** Terrain relief and lens distortion are ignored; positions are as
  good as the published metadata.

## Quick start

Requires Python 3.10 or later, on Linux or macOS.

```bash
make install   # create .venv and install the app with dev tools
make run       # start the app
```

Then open <http://127.0.0.1:8050/>. `make run` calls `scripts/run.sh`, which
creates `.venv` if needed and stops an earlier instance of the app that is
still holding the port.

Without `make`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/lunar-orbiter      # or: .venv/bin/python -m orbiter.app
```

On Windows, use `.venv\Scripts\python -m orbiter.app`.

## Configuration

Settings live in `config.json` at the project root:

```json
{
  "host": "127.0.0.1",
  "port": 8050,
  "language": "es"
}
```

| Key        | Meaning                                  |
|------------|------------------------------------------|
| `host`     | Interface the server listens on          |
| `port`     | Server port                              |
| `language` | Default interface language: `es` or `en` |

Set `ORBITER_CONFIG` to use another file, and `ORBITER_CACHE_DIR` to move the
download cache (default: `data/lpi`).

## Downloads and attribution

The first time a mission is shown, the app downloads the LPI page and small
thumbnail of each of its frames (about 200 per mission) and caches them in
`data/lpi/`, so later runs work from disk. Downloads use three workers and at
most four requests per second. Frame previews are fetched on demand and kept in
a small in-memory cache. Nothing downloaded is committed to the repository.

The disk cache never expires, since the archive does not change. Delete
`data/lpi/` (or one frame's files in it) to download again. Frames that failed
are retried the next time the app starts.

Check the LPI terms of use before automating requests or redistributing images,
and keep the source URL and attribution metadata that the archive publishes.

## Development

```bash
make test     # pytest
make lint     # Ruff lint and format check
make format   # apply Ruff fixes and formatting
make check    # lint + test
make icons    # build favicon and icons from assets/icon.png and logo.png
make help     # list all targets
```

Public functions and classes need Google-style docstrings, which Ruff checks.
State units (degrees, km), optional fields, caching and raised exceptions.

Project layout:

| Path                       | Purpose                                             |
|----------------------------|-----------------------------------------------------|
| `orbiter/app.py`           | Dash layout and callbacks                           |
| `orbiter/globe.py`         | Plotly globe: sphere, photo mosaic, markers         |
| `orbiter/catalog.py`       | Background mission download with on-disk cache      |
| `orbiter/lpi.py`           | LPI page client and parser                          |
| `orbiter/i18n.py`          | Interface text in Spanish and English               |
| `orbiter/reference.py`     | Moon and Lunar Orbiter program tabs                 |
| `orbiter/config.py`        | `config.json` loader                                |
| `orbiter/assets/style.css` | Styles (served automatically by Dash)               |
| `assets/`                  | Brand images: `icon.png` and `logo.png` (sources)   |
| `orbiter/assets/icon.png`  | App icon; `make icons` builds it and the favicons   |
| `scripts/run.sh`           | Launch script used by `make run`                    |
| `site/`                    | Static project page, deployed to GitHub Pages       |

## License

The code is released under the [MIT License](LICENSE), © 2026
[ENERGYCODE](https://www.energycode.org/). Maintainer:
<energycode.org@gmail.com>.

The MIT license covers this project's code only. LPI images and metadata belong
to their respective owners. The reference tabs summarise Wikipedia articles
([Luna](https://es.wikipedia.org/wiki/Luna),
[Lunar Orbiter program](https://en.wikipedia.org/wiki/Lunar_Orbiter_program))
and that text is available under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## Citation

If you use this software, cite it as **ENERGYCODE (2026), _Lunar Orbiter
Atlas_, version 0.1.0**. GitHub can generate a formatted citation from
[`CITATION.cff`](CITATION.cff).

For photographs or metadata, cite the Lunar and Planetary Institute's Lunar
Orbiter Photo Gallery and the individual frame record used. The software
citation does not replace image attribution or the LPI's usage terms.

## Project page

`site/` is a static, bilingual page about the project, published by the
`Pages` workflow on every push to `main` that touches it. Enable it once in
the repository settings: **Settings → Pages → Source: GitHub Actions**. The page
cannot run the atlas itself, which needs a Python server; it links to the
instructions above. Its screenshots live in `site/assets/screens/`.
