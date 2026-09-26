# Lunar Orbiter Atlas

A local web app for exploring the photographs of NASA's Lunar Orbiter missions
(1966–1967) on an interactive 3D Moon. Images and metadata come from the
[Lunar and Planetary Institute (LPI) Lunar Orbiter Photo Gallery](https://www.lpi.usra.edu/resources/lunarorbiter/).

Repository: <https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS>

## Features

- **Mission mosaic** — every frame of the selected mission is drawn on the
  globe at its principal point, sized from the spacecraft altitude. Click a
  photo to hide it and show its details; **Show hidden** brings them back.
- **Frame details** — LPI preview, principal point, spacecraft altitude and
  position, and illumination angles (sun azimuth, incidence, emission, phase).
- **Reference tabs** — summarised facts about the Moon and the Lunar Orbiter
  program, with their Wikipedia sources.
- **English and Spanish** — switch with the **ES | EN** control in the top bar
  (or open `?lang=en` / `?lang=es`).
- Equator and north/south poles are marked on the globe.

Photo placement is approximate: each frame is a north-up patch centred on its
principal point, not a map-projected mosaic.

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
| `scripts/run.sh`           | Launch script used by `make run`                    |

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
