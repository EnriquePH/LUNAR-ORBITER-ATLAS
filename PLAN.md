# Plan

## Hecho

- [x] Fase 1 — errores del callback, coordenadas N/S/E/W, tests de callbacks.
- [x] Fase 2 — globo con Plotly (rotación en el navegador, foto proyectada como textura).
- [x] Fase 3 — metadatos de nave e iluminación, selectores de misión y fotograma.
- [x] Fase 4 — CSS en `assets/`, Ruff con `E501` y formato.
- [x] Mosaico de la misión en la esfera (caché en `data/lpi/`, una sola malla),
      click para ocultar, «Mostrar ocultas (n)», marcas N/S y ecuador.
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

## Pendiente


- [ ] Hacer push y comprobar la primera ejecución de la CI y del despliegue de
      Pages (activar antes Settings → Pages → Source: GitHub Actions).
- [ ] Las tomas oblicuas de gran altitud (p. ej. las de la Tierra de las misiones
      1–3) quedan deformadas: valorar marcarlas u ocultarlas por defecto.
