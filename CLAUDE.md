# CLAUDE.md

Lunar Orbiter Atlas: visor local (Dash) de las fotos del archivo Lunar Orbiter del LPI
(<https://www.lpi.usra.edu/resources/lunarorbiter/>) sobre una esfera lunar 3D, con
pestañas de datos de la Luna y del programa, en español e inglés.
Repo: <https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS> · Licencia MIT, © ENERGYCODE.
Versión 1.0.0 (publicada; notas en [CHANGELOG.md](CHANGELOG.md)). Tareas pendientes y
hechas: [PLAN.md](PLAN.md).

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
  Callbacks: `update_frame` (5 salidas), `render_globe` (4: figura, `focused-frame`,
  `globe-camera`, `clicked-frame`), `list_mission_frames` (arranca
  el `LOADER`), `poll_mosaic` (Interval), `select_clicked_image` (el click solo
  selecciona la foto; **no la oculta**), `select_frame`, `select_random_frame`,
  `export_csv`, `export_geojson` (`dcc.Download`) y `remember_camera`. Se prueban
  llamándolos directamente.
  **Cámara**: `uirevision` es fijo y `render_globe` reenvía siempre la vista del
  usuario (`globe-camera`, desde `relayoutData`), así que redibujar no la mueve.
  Solo una selección nueva que no viene de un click (`clicked-frame`) gira hacia
  la foto conservando la distancia (`focus_camera`); `focused-frame` evita
  repetir el giro al llegar teselas. `remember_camera` también parchea la cámara
  en la figura (`Patch`): al cambiar de pestaña el gráfico se desmonta y vuelve
  desde su `figure`.
- `orbiter/globe.py` — figura Plotly: esfera base, **todas las teselas en un único
  `Mesh3d`** (200 `Surface` congelan el navegador), foto seleccionada como `Surface`,
  marcador, etiqueta con el ID en el centro de cada foto (`_frame_labels`; la
  seleccionada en naranja; interruptor `show-labels`), contorno de fotos de gran
  altitud (>`HIGH_ALTITUDE_KM`), ecuador y polos (`hoverinfo="skip"` para no
  robar clicks). Radios: teselas 1,003–1,0054, seleccionada 1,006, etiquetas
  1,008, marcador 1,009; la cámara no baja de 1,01 (`rotation.js`).
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
  resolución con un tope de `MESH_VERTEX_BUDGET`. El click selecciona la foto
  del hover: el `customdata` (ID por vértice) del `Mesh3d`, que va como
  **lista** y no binario, porque Dash lo relee de la figura por índice.
  `image_at`/`patch_contains` (geometría) quedan como API pública sin uso en la app.
  `frame_geometry` (huella en km, emisión implícita) y `footprint_outline`
  buscan el limbo por bisección desde el punto principal (`_border_distances`):
  cerca del limbo la proyección es singular y una rejilla se queda corta.
- `orbiter/export.py` — CSV de metadatos y GeoJSON de huellas (grados
  selenográficos, no WGS 84; anillos antihorarios, longitudes continuas y
  cierre por el polo si lo rodean).
- `orbiter/catalog.py` — `MissionLoader` descarga en hilos todas las fotos de una
  misión; `TileStore` cachea página+miniatura en `data/lpi/` (escritura atómica,
  sin caducidad: se recarga borrando la carpeta; `metadata()` lee el JSON sin
  descargar), 3 workers con un límite compartido de 4 peticiones/s.
- `orbiter/lpi.py` — cliente y parser del LPI; el parser devuelve `FrameMetadata`
  (`TypedDict`). Errores como `LpiError(key, **params)` que la app traduce con
  `describe_error`. `clear_cache()` vacía las `lru_cache` (lo usa `conftest.py`).
- `orbiter/i18n.py` — todos los textos de la UI en `TEXTS["es"|"en"]`; `t(lang, key)`.
- `orbiter/reference.py` — pestañas «La Luna» y «Programa Lunar Orbiter»
  (`CONTENT["es"|"en"]`), texto CC BY-SA 4.0 resumido de Wikipedia.
- `orbiter/assets/rotation.js` — antes de que Plotly procese un click o la rueda
  en el globo, escala `rotateSpeed` y `zoomSpeed` con la altura sobre la
  superficie, limita el zoom a 1,01 radios (`view.setDistanceLimits`) y ajusta el
  plano de recorte (`glplot.zNear`) al 15 % de la altura (0,01 de lejos, como
  Plotly: más cerca pierde precisión de profundidad y las teselas parpadean).
  Radio en unidades de cámara = `aspectratio / rango del eje` (0,4), no
  `dataScale`. Usa internos de Plotly (`_fullLayout.scene._scene`): revísalo si
  se actualiza.
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
  No puede ejecutar la app (necesita servidor Python). Las capturas `atlas`,
  `mission-4` y `mobile` se regeneran con `draft/scripts/site_screenshots.py`
  (CDP, local: `draft/` no está en git) y se pasan a WebP calidad 82.

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
- Para manejar la UI por CDP: `window.dash_clientside.set_props(id, {...})` cambia
  misión, fotograma o pestaña sin clicks; un click en una foto se simula con
  `set_props('globe', {clickData: {points: [{customdata: ID}]}})`. El hover 3D se
  dibuja en `#globe g.hovertext`, no en `.hoverlayer`. Con la misión 4 espera a que
  termine el redibujado (varios segundos) antes de leer el hover.

## Release

1. Sube la versión en `pyproject.toml`, `CITATION.cff` (`version`,
   `date-released`), la cita del README y `USER_AGENT` en `orbiter/lpi.py`.
2. Añade la sección en `CHANGELOG.md`; `make check` y `make lint-md`.
3. Regenera las capturas de la web si cambió la UI.
4. Commit, `git tag -a vX.Y.Z`, `git push origin main vX.Y.Z`; espera la CI y
   `gh release create vX.Y.Z --notes-file` con la sección del CHANGELOG.
   Un tag ya publicado no se mueve: los arreglos van en una versión nueva.
