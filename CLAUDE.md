# CLAUDE.md

Visor local (Dash) de fotogramas del archivo Lunar Orbiter del LPI
(<https://www.lpi.usra.edu/resources/lunarorbiter/>) proyectados sobre una esfera
lunar 3D.

## Comandos

Usa siempre el entorno `.venv` (Python 3.14; el proyecto declara >=3.10):

```bash
.venv/bin/python -m pip install -e ".[dev]"   # instalar
.venv/bin/python -m orbiter.app               # app en http://127.0.0.1:8050
.venv/bin/pytest                              # tests
.venv/bin/ruff check .                        # lint
```

## Estructura

- `orbiter/urls.py` — constantes y constructores de URL del LPI (`mission_url`, `frame_url`).
- `orbiter/lpi.py` — cliente HTTP + parser HTML (BeautifulSoup + regex sobre el texto).
  `fetch_frame` valida el ID y delega en `_fetch_frame_cached` (`lru_cache(16)`).
  Devuelve el dataclass inmutable `OrbiterFrame`; los campos de nave e iluminación
  (`_OPTIONAL_FIELDS`) son opcionales y quedan en `None` si la página no los trae.
  `fetch_mission_frames` lista los IDs de una misión (`lru_cache`, 1–5).
- `orbiter/app.py` — app Dash: CSS inline en `app.index_string`, layout y tres callbacks:
  `list_mission_frames` (misión → opciones), `select_frame` (opción → input `frame-id`)
  y `update_frame` (5 salidas; se dispara con el botón, con Intro en el input o al
  elegir fotograma). Los desplegables de Dash 4 se tematizan con variables `--Dash-*`. `make_globe` devuelve una `go.Figure` de Plotly: esfera
  base + parche `go.Surface` con la textura del fotograma (`surfacecolor`) + marcador,
  con la cámara centrada en el punto principal. La rotación es en el navegador.
  El parche es esquemático (`PATCH_WIDTH_DEGREES` fijo), no un mosaico cartográfico.
- `tests/` — pytest; la red se simula con `monkeypatch` sobre `orbiter.lpi.requests.get`
  (o sobre `orbiter.app.fetch_*` en los tests de callbacks, que se llaman directamente).
- `LUNAR ORBITER.ipynb` — cuaderno exploratorio original (2020). Excluido de Ruff; no
  modificar salvo petición expresa.

## Convenciones

- Textos de UI, mensajes de error y README en **español**; identificadores y docstrings en inglés.
- Los tests nunca deben hacer peticiones reales al LPI. Como `_fetch_frame_cached` es
  una caché global, usa IDs distintos por test o limpia la caché (`cache_clear()`).
- No guardar imágenes descargadas en el repo (`/data/` y `/outputs/` están en `.gitignore`).
  La licencia MIT cubre solo el código, no el material del LPI.
- Sé conservador con peticiones al LPI (caché, timeouts, un fotograma por acción).
- Ruff: `line-length = 88`, pero `E501` no está activado; reglas en `pyproject.toml`.
- Un callback de Dash con N `Output` debe devolver siempre N valores (también en ramas de error).
- Para comprobar la UI: `chromium-browser --headless` (snap: no escribe en `/tmp`, usa
  `outputs/`). Al parar la app, mata el PID concreto: `pkill -f orbiter.app` también mata
  el propio shell y deja servidores viejos ocupando el puerto 8050.
