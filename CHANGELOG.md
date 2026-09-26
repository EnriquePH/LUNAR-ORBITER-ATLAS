# Changelog

All notable changes to Lunar Orbiter Atlas are listed here. Versions follow
[Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-09-26

First release.

### Atlas

- Mission mosaic: every frame of the selected mission (890 frames over the
  five missions) is projected from the spacecraft onto the part of the Moon
  it photographed, with the 80 mm or 610 mm camera. Oblique and high-altitude
  shots cover the area they really saw; pixels past the limb are dropped.
- Estimated image roll: near-vertical frames north-up, oblique frames level
  with the horizon, high-altitude frames turned to match their black sky.
- Frame IDs labelled at the centre of each photo, with the selected one in
  orange; a **Labels** switch hides them and is remembered.
- Rotation slows down as you zoom in, and the zoom stops just above the
  surface, so photos stay easy to pick up close.
- Click a photo, pick one from the selector, type its ID or press **Random**
  to show it in the side panel.
- Side panel: LPI preview, principal point, spacecraft position and altitude,
  illumination angles, camera, ground footprint in km, and a check of the
  LPI's emission angle against the one implied by the spacecraft position.
- Export the loaded frames of a mission as CSV (metadata and geometry) or
  GeoJSON (projected footprints, closed round the poles and cut at the limb).
- Equator, poles and an outline for frames taken above 1000 km.

### Interface

- English and Spanish, switched with **ES | EN** or `?lang=`, and remembered
  in the browser.
- Reference tabs on the Moon and the Lunar Orbiter program, summarised from
  Wikipedia (CC BY-SA 4.0).
- DM Mono throughout, brand icon and favicons; works on phone-sized screens.

### Data and tooling

- Background download of whole missions with an on-disk cache in `data/lpi`,
  three workers and at most four requests per second; `make download`
  pre-fills it.
- Public coordinate conversions (`selenographic_to_cartesian`,
  `cartesian_to_selenographic`).
- `config.json` for host, port and default language; `lunar-orbiter` command,
  `scripts/run.sh` and a `Makefile`.
- Google-style docstrings checked by Ruff, pytest suite, CI on Python 3.10 and
  3.14, and a bilingual project page on GitHub Pages.

[1.0.0]: https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS/releases/tag/v1.0.0
