# Plan

## Hecho

- [x] Fase 1 — errores del callback, coordenadas N/S/E/W, tests de callbacks.
- [x] Fase 2 — globo con Plotly (rotación en el navegador, textura a resolución real).
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

## Pendiente

- [ ] Comprobar la primera ejecución de la CI en GitHub (en local pasan los tests
      con Python 3.10 y 3.14).
- [ ] Probar el mosaico de las misiones 2–5 (solo la 1 se ha descargado entera;
      de la 3 solo se probó la lista de fotogramas). Las misiones 4 y 5 tienen órbitas polares altas y fotos
      mucho mayores: revisar cómo se ven y si hace falta ajustar `MAX_PATCH_DEGREES`.
- [ ] Revisar con datos reales la aproximación del tamaño de cada foto
      (`FOOTPRINT_PER_ALTITUDE`), que asume toma vertical; las oblicuas quedan
      deformadas.
- [ ] Opcional: recordar el idioma elegido entre visitas y fijar el atributo `lang`
      del documento HTML.
