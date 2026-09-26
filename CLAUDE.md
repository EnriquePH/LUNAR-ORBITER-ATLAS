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
make stop      # scripts/run.sh --stop: para solo el visor de ese puerto
make download  # precarga data/lpi (python -m orbiter.catalog; MISSIONS="1 4")
make site      # sirve site/ en http://127.0.0.1:8765/
make lint-md   # pymarkdownlnt vía uvx (sin MD013)
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
  Dos callbacks clientside guardan la elección en `localStorage` y la recuperan
  si se entra sin `?lang=`; también fijan `<html lang>`.
  Callbacks: `update_frame` (5 salidas), `render_globe`, `list_mission_frames` (arranca
  el `LOADER`), `poll_mosaic` (Interval), `select_clicked_image` (el click solo
  selecciona la foto; **no la oculta**), `select_frame`, `select_random_frame`,
  `export_csv` y `export_geojson` (`dcc.Download`). Se prueban llamándolos
  directamente.
- `orbiter/globe.py` — figura Plotly: esfera base, **todas las teselas en un único
  `Mesh3d`** (200 `Surface` congelan el navegador), foto seleccionada como `Surface`,
  marcador, etiqueta con el ID en el centro de cada foto (`_frame_labels`; la
  seleccionada en naranja), contorno de fotos de gran altitud (>`HIGH_ALTITUDE_KM`), ecuador y polos
  (`hoverinfo="skip"` para no robar clicks).
  **Proyección** (`frame_camera`): cámara estenopeica desde la posición de la nave hacia
  el punto principal; cada píxel es un rayo que corta la esfera (NaN si no la toca).
  Cámara según la vista previa (`camera_of`): `_med` → 80 mm, 55×65 mm; si no → 610 mm,
  subfotograma central h2. Se rechaza (parche norte-arriba de respaldo) si la emisión
  implicada difiere >5° de la del LPI. Giro: casi verticales norte arriba; oblicuas
  niveladas con horizonte arriba; gran altitud: el giro de 90° cuyo «cielo» cae en
  negro en la miniatura (`_match_sky`, reglas estrictas). Validado contra las 890
  fotos: si cambias estas reglas, superpón el cielo predicho sobre las miniaturas
  (p. ej. 5038, 5041, 1102, 2034, 4114) y compruébalo a ojo.
  Plotly colorea por vértice (1 píxel = 1 vértice): `tile_textures` reparte la
  resolución con un tope de `MESH_VERTEX_BUDGET`. El click se resuelve por geometría
  (`patch_contains` → `FrameCamera.sees`), no por índices de traza.
  `frame_geometry` (huella en km, emisión implícita) y `footprint_outline`
  buscan el limbo por bisección desde el punto principal (`_border_distances`):
  cerca del limbo la proyección es singular y una rejilla se queda corta.
- `orbiter/export.py` — CSV de metadatos y GeoJSON de huellas (grados
  selenográficos, no WGS 84; anillos antihorarios, longitudes continuas y
  cierre por el polo si lo rodean).
- `orbiter/catalog.py` — `MissionLoader` descarga en hilos todas las fotos de una
  misión; `TileStore` cachea página+miniatura en `data/lpi/` (escritura atómica,
  sin caducidad: se recarga borrando la carpeta; `metadata()` lee el JSON sin descargar), 3 workers con un límite
  compartido de 4 peticiones/s.
- `orbiter/lpi.py` — cliente y parser del LPI; el parser devuelve `FrameMetadata`
  (`TypedDict`). Errores como `LpiError(key, **params)` que la app traduce con
  `describe_error`. `clear_cache()` vacía las `lru_cache` (lo usa `conftest.py`).
- `orbiter/i18n.py` — todos los textos de la UI en `TEXTS["es"|"en"]`; `t(lang, key)`.
- `orbiter/reference.py` — pestañas «La Luna» y «Programa Lunar Orbiter»
  (`CONTENT["es"|"en"]`), texto CC BY-SA 4.0 resumido de Wikipedia.
- `orbiter/assets/rotation.js` — antes de que Plotly procese un click o la rueda
  en el globo, escala `camera.rotateSpeed` con la altura sobre la superficie y
  limita el zoom (`view.setDistanceLimits`) para no atravesar la Luna. Usa
  internos de Plotly (`_fullLayout.scene._scene`): revísalo si se actualiza.
- `orbiter/assets/style.css` — todo el CSS. **Única fuente: DM Mono** (pesos 300–500,
  sin 600/700), también en la figura de Plotly. Desplegables de Dash 4 tematizados con
  variables `--Dash-*`; su menú abierto va en un portal fuera de `.side-panel`.
- `scripts/run.sh` — crea `.venv` si falta y para una instancia previa del visor
  que ocupe el puerto (nunca otros programas).
- `.github/workflows/ci.yml` — ruff + pytest con Python 3.10 y 3.14.
- `assets/icon.png` y `assets/logo.png` — imágenes de marca del usuario (fuentes a
  tamaño completo; no las modifiques). `make icons` (`scripts/build_icons.py`, solo
  Pillow) recorta el icono a círculo y genera `orbiter/assets/icon.png`,
  `favicon.ico`, `icon-192.png`, `apple-touch-icon.png` y `site/assets/logo.png`.
  No edites los derivados a mano.
- `site/` — página estática del proyecto para GitHub Pages (`pages.yml` la publica;
  en GitHub: Settings → Pages → Source: GitHub Actions). HTML bilingüe con
  `data-l="en|es"` y `assets/site.js`; capturas en `site/assets/screens/` (WebP).
  No puede ejecutar la app (necesita servidor Python).

## Convenciones

- **No borrar archivos**: muévelos a `draft/` (ignorada por git) conservando su ruta
  relativa, p. ej. `mkdir -p draft/orbiter && mv orbiter/x.py draft/orbiter/`.
- **Idiomas**: la UI es bilingüe; ningún texto visible va escrito en el código, todo
  pasa por `t()` con la misma clave en `es` y `en` (lo comprueba `tests/test_i18n.py`).
  README en **inglés**. Identificadores y docstrings en inglés.
- Los tests nunca hacen peticiones reales al LPI. `lpi.clear_cache()` se llama en
  el fixture `autouse` de `tests/conftest.py`; el `LOADER` de la app se sustituye
  por un `FakeLoader`.
- Sé conservador con el LPI: caché en disco, timeouts, límite de peticiones.
  El User-Agent lleva la web de ENERGYCODE, no emails.
- No subir descargas: `/data/`, `/outputs/` y `/draft/` están en `.gitignore`.
  MIT cubre solo el código; imágenes del LPI y texto de Wikipedia tienen su licencia.
- Ruff: `line-length = 88` con `E501` y `ruff format`.
- Docstrings estilo **Google** obligatorios en la API pública (Ruff `D`; `D107`
  desactivado: los argumentos del constructor van en el docstring de la clase).
  Indica unidades (grados, km), campos opcionales, caché y excepciones.
- Un callback con N `Output` devuelve siempre N valores, también en ramas de error.
- Comprobar la UI: `chromium-browser --headless --remote-debugging-port=9333` (snap:
  no escribe en `/tmp`, usa `outputs/`). Para parar la app usa `make run` (para la
  anterior) o `pgrep -f "python -m orbiter[.]app"`: con `pkill -f orbiter.app` el
  patrón coincide con el propio shell y lo mata.
- En Chromium headless (render por software) los clicks 3D de Plotly fallan a veces:
  tras mover el ratón espera ~1 s y comprueba que el click se registró antes de
  medir tiempos.
