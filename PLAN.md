# Plan

## Hecho

- [x] Fase 1 — errores del callback, coordenadas N/S/E/W, tests de callbacks.
- [x] Fase 2 — globo con Plotly (rotación en el navegador, textura a resolución real).
- [x] Fase 3 — metadatos de nave e iluminación, selectores de misión y fotograma.
- [x] Fase 4 — CSS en `assets/`, extra `notebook`, Ruff con `E501` y formato.

## En curso

- [ ] **Mosaico de la misión en la esfera**: todas las fotos de la misión elegida
      (miniaturas del LPI con caché en `data/lpi/`, 3 descargas en paralelo con un
      máximo de 4 peticiones/s). Click en una foto la oculta y la muestra en el
      panel; «Mostrar ocultas (n)» las recupera. Tamaño de cada foto según la
      altitud de la nave. Pendiente: verificarlo en el navegador tras unir las
      teselas en una sola malla.

## Pendiente

- [ ] **Pestañas de datos**: «Atlas» (vista actual) y una pestaña con los datos
      resumidos de la Luna (<https://es.wikipedia.org/wiki/Luna>) y del programa
      Lunar Orbiter (<https://en.wikipedia.org/wiki/Lunar_Orbiter_program>), con
      atribución CC BY-SA 4.0.
- [ ] **README en inglés** (y ajustar la convención de idioma en `CLAUDE.md`).
- [ ] **Configuración en JSON**: `config.json` con host y puerto (8050) que lea la app.
- [ ] **Script de arranque** que use esa configuración y libere el puerto si lo
      ocupa una instancia anterior de la app.
- [ ] **Makefile** con `install`, `run`, `test`, `lint`, `format` y `clean`.
- [ ] **CI** — falta decidir plataforma: Bitbucket Pipelines o GitHub Actions.
