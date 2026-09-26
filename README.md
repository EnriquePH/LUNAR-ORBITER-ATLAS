# Lunar Orbiter

Aplicación Python local para explorar fotografías del archivo Lunar Orbiter del
Lunar and Planetary Institute (LPI) sobre una esfera lunar 3D.

Fuente: <https://www.lpi.usra.edu/resources/lunarorbiter/>.

## Estado

La aplicación obtiene del LPI la vista previa y las coordenadas del fotograma
seleccionado. La imagen se muestra en el panel y como un parche de textura
aproximado, centrado en las coordenadas del punto principal; no representa un
mosaico cartográfico completo. El cuaderno exploratorio original se conserva.

## Instalación

Requiere Python 3.10 o posterior.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m orbiter.app
```

En Windows, activa el entorno con `.venv\Scripts\activate`.
La aplicación queda disponible en <http://127.0.0.1:8050>.

## Uso

```python
from orbiter.urls import MISSIONS_NUM, frame_url, mission_url

print(MISSIONS_NUM)
print(mission_url(1))
print(frame_url("1041"))
```

Para abrir el cuaderno:

```bash
jupyter lab "LUNAR ORBITER.ipynb"
```

En el visor, elige una misión y uno de sus fotogramas en los selectores, o
introduce un identificador como `1041` y pulsa **Cargar** (o Intro). El panel
muestra el punto principal, la posición y altitud de la nave y los ángulos de
iluminación publicados por el LPI. La esfera se centra en el fotograma; arrástrala para rotarla y usa
la rueda del ratón para acercarte.

## Descargas y atribución

Las imágenes se solicitan al LPI cuando se carga un fotograma y se mantienen en
una caché de memoria limitada a 16 fotogramas (y las listas de las 5 misiones)
para evitar solicitudes repetidas; no se copian al repositorio. Consulta las condiciones de uso antes de
automatizar solicitudes o redistribuir imágenes. Evita cargas innecesarias y
conserva la URL de origen y los metadatos de atribución publicados por el
archivo.

La licencia MIT de este repositorio cubre el código propio, no las imágenes,
metadatos ni otros materiales servidos por el LPI. Los derechos y condiciones de
esos materiales dependen de sus respectivas fuentes.

## Desarrollo

Las herramientas de desarrollo incluidas en el extra `dev` son pytest, Ruff y
Jupyter. Ejecuta las comprobaciones con:

```bash
pytest
ruff check .
```

## Licencia

El código de este proyecto se distribuye bajo la licencia MIT. Consulta
[LICENSE](LICENSE).