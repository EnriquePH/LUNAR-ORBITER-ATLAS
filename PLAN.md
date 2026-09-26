# Plan

## Hecho

- [x] Fase 1 — errores del callback, coordenadas N/S/E/W, tests de callbacks.
- [x] Fase 2 — globo con Plotly (rotación en el navegador, foto proyectada como textura).
- [x] Fase 3 — metadatos de nave e iluminación, selectores de misión y fotograma.
- [x] Fase 4 — CSS en `assets/`, Ruff con `E501` y formato.
- [x] Mosaico de la misión en la esfera (caché en `data/lpi/`, una sola malla),
      marcas N/S y ecuador.
- [x] Pestañas de datos: «Atlas», «La Luna» y «Programa Lunar Orbiter», con
      atribución CC BY-SA 4.0 a Wikipedia.
- [x] App bilingüe ES/EN: selector en la barra superior (`?lang=`), textos en
      `orbiter/i18n.py` y `orbiter/reference.py`.
- [x] `config.json` con host, puerto 8050 e idioma por defecto.
- [x] `scripts/run.sh`, `Makefile` y comando `lunar-orbiter`.
- [x] README en inglés; licencia MIT a nombre de ENERGYCODE.
- [x] CI con GitHub Actions (ruff + pytest, Python 3.10 y 3.14).
- [x] Cuaderno Jupyter retirado a `draft/` junto con sus dependencias.

- [x] Documentación de la API (de `draft/findings.md` e `improvements.md`):
      textura de `globe_image()` descrita como miniatura; `FrameMetadata`
      (`TypedDict`) con unidades y opcionales; caché, errores y `clear_cache()`
      en `lpi.py`; unidades, aproximación y meridiano 180° en `globe.py`;
      contratos de `config.py` e `i18n.py` (y `port: true` ahora se rechaza);
      caché del mosaico documentada (no caduca; borrar `data/lpi` para recargar);
      `urls.py` construye sin validar; Ruff `D` con convención Google.
- [x] Idioma recordado entre visitas (`localStorage`) y atributo `lang` del HTML.
- [x] Tipografía única: DM Mono en toda la app (antes Manrope y Newsreader).
- [x] Mosaico probado con las 5 misiones (890 fotos, 0 fallos; primera descarga
      de 46 s a 108 s por misión). Tamaños revisados con datos reales:
      misiones 1–3 a ~50 km → fotos de 1,2–1,4° (≈ 37–42 km, coherente con la
      cámara de resolución media); misión 4 a 2700–5800 km → las 131 fotos llegan
      al tope de 30° y forman un mapa de cobertura de la cara visible; misión 5
      mezcla 130 primeros planos (~100–130 km) y 30 tomas altas de la cara oculta.
      `MAX_PATCH_DEGREES` se mantiene en 30°. Etiquetas N/S separadas del limbo.
- [x] Icono y logo del usuario (`assets/icon.png`, `assets/logo.png`) como imagen de
      marca: favicon e iconos con `make icons`, icono en la barra de la app, logo en
      la web. (Mi primer logo SVG está en `draft/`.)
- [x] Página del proyecto en `site/` para GitHub Pages (bilingüe, capturas, cómo
      ejecutarla, fuentes y licencias) y workflow `pages.yml`.
- [x] Texturas según el tamaño de cada foto: 3 px/grado entre 10 y 48 px, con un
      tope de 90 000 vértices para todo el mosaico (`tile_textures`). Las misiones
      1–3 pesan un 32–70 % menos; las fotos grandes pasan de 20 a 48 px (30 px en la
      misión 4, que va al tope: 87 000 vértices, 5,4 MB de figura). Coste medido:
      +0,17 s en servidor y +0,3–0,6 s de redibujado con render por software.
- [x] Fotos proyectadas desde la nave sobre la parte de la Luna que fotografiaron
      (cámara de 80 mm o 610 mm según la vista previa; validado con 890 fotos, 22
      con metadatos incoherentes usan el parche). Orientación estimada: oblicuas con
      horizonte arriba; gran altitud girada según el cielo de la imagen. Contorno y
      aviso para tomas de más de 1000 km. S del polo sur a la misma distancia que N.
- [x] Badges en el README.

- [x] Push, CI en verde (Python 3.10 y 3.14) y web publicada en
      <https://enriqueph.github.io/LUNAR-ORBITER-ATLAS/>. Acciones de GitHub
      actualizadas a versiones con Node 24.

- [x] El click en una foto ya no la oculta: solo la selecciona y muestra sus datos
      (se retiran «Mostrar ocultas» y el estado de fotos ocultas).

- [x] Makefile: `stop`, `download` (precarga de fotos), `site` (web en local) y
      `lint-md`.

- [x] Ideas baratas de `draft/ideas-de-mejora.md`:
      1. Conversión de coordenadas pública (`selenographic_to_cartesian`,
         `cartesian_to_selenographic`) con tests de ida y vuelta.
      2. Panel lateral: cámara (80 / 610 mm), huella en km y comprobación de la
         emisión (LPI frente a la calculada, Δ; aviso si supera 5°).
      3. Botón «Al azar» con un fotograma de la misión.
      4. Exportar la misión: CSV (metadatos del caché + cámara, huella, emisión
         calculada) y GeoJSON (huellas). El contorno y la huella buscan el limbo
         por bisección: con una rejilla quedaban hasta 12° por dentro. Probado
         con las 890 fotos: 5 tomas de 5500 km ven el disco entero y varias de
         la misión 4 y 5 rodean un polo (anillo cerrado por lat ±90). <1 s por
         misión.
- [x] README revisado: funciones nuevas, formato de las exportaciones y tabla
      de módulos (`export.py`, `urls.py`). Deshecho un formateo del editor que
      quitaba espacios (diff guardado en `draft/README-editor-format.diff`).
- [x] Capturas de la web regeneradas (`atlas`, `mission-4` con la toma 4114,
      `mobile`) con los botones nuevos; script CDP en
      `draft/scripts/site_screenshots.py`. Corregido en móvil el solapamiento de
      la leyenda y la nota bajo el globo, y de la etiqueta superior con la «N».
- [x] Etiqueta con el ID en el centro de cada foto del globo (una sola traza
      `Scatter3d` de texto, sin hover para no robar clicks); la de la foto
      seleccionada (la del panel) pasa a naranja sobre su marcador.
- [x] Interruptor «Etiquetas» sobre el globo (recordado en el navegador).
- [x] Giro más lento al acercarse (proporcional a la altura sobre la superficie)
      y zoom limitado justo encima de la Luna (`orbiter/assets/rotation.js`).
      Medido: el mismo arrastre de 100 px gira 22° de cerca antes y 0,8° ahora.
- [x] La vista ya no salta al hacer click en una foto: `uirevision` fijo y la
      cámara del usuario se reenvía en cada redibujado. Elegir una foto por
      otra vía (selector, ID, al azar) gira hacia ella manteniendo el zoom.
- [x] La vista se conserva al cambiar de pestaña (la cámara se parchea en la
      figura con `Patch`).
- [x] Zoom hasta ~17 km sobre la superficie (1,01 radios) con plano de recorte
      cercano reducido; corregido el radio usado por `rotation.js` (0,4, no 0,495).
- [x] El click selecciona la foto del hover (`customdata` del mosaico como lista:
      Dash lo relee de la figura por índice y fallaba con el array binario).
- [x] Logo de la app enlazado a la web del proyecto y enlace «GITHUB ↗» al repo.
- [x] Revisión previa a la release: plano de recorte adaptativo (0,01 de lejos,
      como Plotly, para no perder precisión de profundidad), README y CHANGELOG
      reordenados, capturas de la web con el enlace a GitHub.
- [x] Release 1.0.0 publicada el 2026-09-26: versión en `pyproject.toml`,
      `CITATION.cff`, README y User-Agent; `CHANGELOG.md`; tag `v1.0.0` en
      `8b16f1c`; release en GitHub con las notas del CHANGELOG
      (<https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS/releases/tag/v1.0.0>).
      CI (3.10 y 3.14) y Pages en verde.

## Pendiente

- (nada abierto)

## Ideas para después de 1.0.0 (sin compromiso)

- Etiquetas: en la franja ecuatorial de la misión 1 se amontonan y sobre fotos
  claras contrastan poco (probar contorno oscuro u ocultar las que se solapan).
- De cerca (~17 km) la textura se ve borrosa: la foto seleccionada usa la vista
  previa reducida a 256 px. Se podría cargar a más resolución al acercarse.
- `image_at` y `patch_contains` ya no los usa la app (el click va por
  `customdata`); decidir si se mantienen como API pública o van a `draft/`.
