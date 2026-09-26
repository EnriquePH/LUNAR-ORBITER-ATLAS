# CLAUDE.md

Lunar Orbiter Atlas: visor local (Dash) de las fotos del archivo Lunar Orbiter del LPI
(<https://www.lpi.usra.edu/resources/lunarorbiter/>) sobre una esfera lunar 3D, con
pestañas de datos de la Luna y del programa, en español e inglés.
Repo: <https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS> · Licencia MIT, © ENERGYCODE.
Tareas pendientes y hechas: [PLAN.md](PLAN.md).

## Comandos

Usa el `Makefile` (envuelve `.venv`, Python 3.14 local; el proyecto declara >=3.10):

```bash
make install   # .venv + pip install -e ".[dev]"
make run       # scripts/run.sh: arranca en host/puerto de config.json (8050)
make check     # ruff check + ruff format --check + pytest (lo mismo que la CI)
make format    # ruff --fix + ruff format (obligatorio antes de commit)
```

## Estructura

- `config.json` + `orbiter/config.py` — `host`, `port` (8050) e idioma por defecto;
  `load_config()` valida y rechaza claves desconocidas. `ORBITER_CONFIG` cambia el archivo.
- `orbiter/app.py` — Dash. `app.layout` es solo `dcc.Location` + `#page`; el callback
  `render_page` monta `serve_layout(lang)` según `?lang=` (el layout no puede leer la
  query: Dash lo pide por `/_dash-layout`). Por eso `suppress_callback_exceptions=True`
  y `app.validation_layout`. El idioma viaja en `dcc.Store("lang")` como `State`.
  Callbacks: `update_frame` (5 salidas), `render_globe`, `list_mission_frames` (arranca
  el `LOADER`), `poll_mosaic` (Interval), `hide_clicked_image`, `show_hidden`,
  `describe_hidden`, `select_frame`. Se prueban llamándolos directamente.
- `orbiter/globe.py` — figura Plotly: esfera base, **todas las teselas en un único
  `Mesh3d`** (200 `Surface` congelan el navegador), foto seleccionada como `Surface` a
  más resolución, marcador, ecuador y polos N/S (`hoverinfo="skip"` para que no roben
  clicks). Tamaño de cada foto según la altitud de la nave (`patch_width_degrees`).
  El click se resuelve por geometría (`image_at`), no por índices de traza.
- `orbiter/catalog.py` — `MissionLoader` descarga en hilos todas las fotos de una
  misión; `TileStore` cachea página+miniatura en `data/lpi/` (escritura atómica),
  3 workers con un límite compartido de 4 peticiones/s.
- `orbiter/lpi.py` — cliente y parser del LPI. Errores como `LpiError(key, **params)`
  que la app traduce con `describe_error`.
- `orbiter/i18n.py` — todos los textos de la UI en `TEXTS["es"|"en"]`; `t(lang, key)`.
- `orbiter/reference.py` — pestañas «La Luna» y «Programa Lunar Orbiter»
  (`CONTENT["es"|"en"]`), texto CC BY-SA 4.0 resumido de Wikipedia.
- `orbiter/assets/style.css` — todo el CSS. Desplegables de Dash 4 tematizados con
  variables `--Dash-*`; su menú abierto va en un portal fuera de `.side-panel`.
- `scripts/run.sh` — crea `.venv` si falta y para una instancia previa del visor
  que ocupe el puerto (nunca otros programas).
- `.github/workflows/ci.yml` — ruff + pytest con Python 3.10 y 3.14.

## Convenciones

- **No borrar archivos**: muévelos a `draft/` (ignorada por git) conservando su ruta
  relativa, p. ej. `mkdir -p draft/orbiter && mv orbiter/x.py draft/orbiter/`.
- **Idiomas**: la UI es bilingüe; ningún texto visible va escrito en el código, todo
  pasa por `t()` con la misma clave en `es` y `en` (lo comprueba `tests/test_i18n.py`).
  README en **inglés**. Identificadores y docstrings en inglés.
- Los tests nunca hacen peticiones reales al LPI. Las `lru_cache` de `lpi.py` se
  limpian en el fixture `autouse` de `tests/conftest.py`; el `LOADER` de la app se
  sustituye por un `FakeLoader`.
- Sé conservador con el LPI: caché en disco, timeouts, límite de peticiones.
  El User-Agent lleva la web de ENERGYCODE, no emails.
- No subir descargas: `/data/`, `/outputs/` y `/draft/` están en `.gitignore`.
  MIT cubre solo el código; imágenes del LPI y texto de Wikipedia tienen su licencia.
- Ruff: `line-length = 88` con `E501` y `ruff format`.
- Un callback con N `Output` devuelve siempre N valores, también en ramas de error.
- Comprobar la UI: `chromium-browser --headless --remote-debugging-port=9333` (snap:
  no escribe en `/tmp`, usa `outputs/`). Para parar la app usa `make run` (para la
  anterior) o `pgrep -f "python -m orbiter[.]app"`: con `pkill -f orbiter.app` el
  patrón coincide con el propio shell y lo mata.
