"""Local Dash app for viewing Lunar Orbiter frames on a 3D lunar globe."""

from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
import requests
from dash import Dash, Input, Output, State, dcc, html, no_update
from PIL import Image

from orbiter.catalog import MissionLoader, TileStore, default_cache_dir
from orbiter.globe import (
    GlobeImage,
    format_coordinates,
    image_at,
    make_globe,
    visible_images,
)
from orbiter.lpi import OrbiterFrame, fetch_frame, fetch_mission_frames
from orbiter.urls import MISSIONS_NUM, frame_url

DEFAULT_FRAME_ID = "1041"
DEFAULT_MISSION = 1
TEXTURE_SIZE = (256, 256)
# Re-render the globe after this many new tiles while a mission is loading.
MOSAIC_RENDER_STEP = 25

LOADER = MissionLoader(TileStore(default_cache_dir()))


def _thumbnail(image_bytes: bytes) -> Image.Image:
    image = Image.open(BytesIO(image_bytes)).convert("L")
    image.thumbnail(TEXTURE_SIZE, Image.Resampling.LANCZOS)
    return image


def globe_image(frame: OrbiterFrame) -> GlobeImage:
    """Convert a fetched frame into a high-resolution globe texture."""
    return GlobeImage(
        frame_id=frame.frame_id,
        latitude=frame.latitude,
        longitude=frame.longitude,
        altitude_km=frame.spacecraft_altitude_km,
        texture=np.asarray(_thumbnail(frame.image_bytes), dtype=np.uint8),
    )


def _metadata_row(label: str, value: str = "—") -> html.Div:
    return html.Div(
        [
            html.Span(label, className="meta-label"),
            html.Span(value, className="meta-value"),
        ],
        className="meta-row",
    )


def _degrees(*values: float | None) -> str:
    if any(value is None for value in values):
        return "—"
    return "  /  ".join(f"{value:.2f}°" for value in values)


def metadata_rows(frame: OrbiterFrame) -> list[html.Div]:
    """Build the side-panel rows; fields missing from the LPI page show "—"."""
    spacecraft_position = "—"
    if frame.spacecraft_latitude is not None and frame.spacecraft_longitude is not None:
        spacecraft_position = format_coordinates(
            frame.spacecraft_latitude, frame.spacecraft_longitude
        )
    altitude = (
        "—"
        if frame.spacecraft_altitude_km is None
        else f"{frame.spacecraft_altitude_km:.2f} km"
    )
    return [
        _metadata_row("MISIÓN", frame.mission),
        _metadata_row("FOTOGRAMA", frame.frame_id),
        _metadata_row(
            "PUNTO PRINCIPAL", format_coordinates(frame.latitude, frame.longitude)
        ),
        _metadata_row("ALTITUD DE LA NAVE", altitude),
        _metadata_row("POSICIÓN DE LA NAVE", spacecraft_position),
        _metadata_row("ACIMUT SOLAR", _degrees(frame.sun_azimuth)),
        _metadata_row(
            "INCIDENCIA / EMISIÓN",
            _degrees(frame.incidence_angle, frame.emission_angle),
        ),
        _metadata_row("ÁNGULO DE FASE", _degrees(frame.phase_angle)),
    ]


FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500"
    "&family=Manrope:wght@400;500;600;700"
    "&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap"
)

app = Dash(__name__, external_stylesheets=[FONTS_URL])
app.title = "Lunar Orbiter | Atlas"


app.layout = html.Div(
    [
        dcc.Interval(id="initial-load", interval=500, n_intervals=0, max_intervals=1),
        dcc.Interval(id="mosaic-poll", interval=1000, disabled=True),
        dcc.Store(id="selected-frame"),
        dcc.Store(id="hidden-frames", data=[]),
        dcc.Store(id="mosaic-count", data=0),
        html.Header(
            [
                html.Div(
                    [
                        html.Div("LO", className="brand-mark"),
                        html.Div(
                            ["LUNAR ORBITER", html.Br(), "PHOTO ARCHIVE / FIELD ATLAS"],
                            className="brand-copy",
                        ),
                    ],
                    className="wordmark",
                ),
                html.Div(
                    "LPI DIGITAL ARCHIVE     ·     LOCAL VIEWER", className="top-meta"
                ),
            ],
            className="topbar",
        ),
        html.Section(
            [
                html.Div(
                    [
                        html.Div(
                            "EXPLORACIÓN FOTOGRÁFICA · 1966—1967", className="eyebrow"
                        ),
                        html.H1("Atlas orbital lunar"),
                    ]
                ),
                html.Div(
                    "Fotogramas históricos del archivo LPI proyectados sobre "
                    "una esfera interactiva.",
                    className="title-note",
                ),
            ],
            className="page-title",
        ),
        html.Main(
            [
                html.Section(
                    [
                        html.Div(
                            "VISTA 3D  /  ARRASTRA PARA ROTAR · CLICK EN UNA FOTO PARA "
                            "OCULTARLA",
                            className="globe-label",
                        ),
                        dcc.Graph(
                            id="globe",
                            figure=make_globe(),
                            className="globe-render",
                            config={"displayModeBar": False, "responsive": True},
                        ),
                        html.Div(
                            "POSICIÓN Y TAMAÑO APROXIMADOS · ORIENTACIÓN NORTE ARRIBA",
                            className="globe-coordinates",
                        ),
                    ],
                    className="globe-panel",
                ),
                html.Aside(
                    [
                        html.Div(
                            [
                                html.Div(
                                    "ARCHIVO DE IMÁGENES", className="section-kicker"
                                ),
                                html.H2("Fotograma", className="side-heading"),
                            ],
                            className="source-block",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            id="mission-select",
                                            options=[
                                                {
                                                    "label": f"Lunar Orbiter {number}",
                                                    "value": number,
                                                }
                                                for number in range(1, MISSIONS_NUM + 1)
                                            ],
                                            value=DEFAULT_MISSION,
                                            placeholder="MISIÓN",
                                            clearable=False,
                                            searchable=False,
                                        ),
                                        dcc.Dropdown(
                                            id="frame-select",
                                            options=[],
                                            placeholder="FOTOGRAMA",
                                            disabled=True,
                                        ),
                                    ],
                                    className="selector-row",
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            "PREPARANDO MOSAICO…",
                                            id="mosaic-status",
                                            className="status-line",
                                        ),
                                        html.Button(
                                            "MOSTRAR OCULTAS",
                                            id="show-hidden",
                                            n_clicks=0,
                                            disabled=True,
                                            className="text-button",
                                        ),
                                    ],
                                    className="mosaic-row",
                                ),
                                html.Div(
                                    [
                                        dcc.Input(
                                            id="frame-id",
                                            value=DEFAULT_FRAME_ID,
                                            type="text",
                                            className="frame-input",
                                            debounce=True,
                                            inputMode="numeric",
                                        ),
                                        html.Button(
                                            "Cargar ↗",
                                            id="load-frame",
                                            n_clicks=0,
                                            className="load-button",
                                        ),
                                    ],
                                    className="control-row",
                                ),
                                html.Div(
                                    "CONECTANDO CON EL ARCHIVO LPI…",
                                    id="status",
                                    className="status-line",
                                ),
                            ],
                            className="source-block",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    html.Img(
                                        id="preview",
                                        className="preview-image",
                                        alt="Vista previa del fotograma Lunar Orbiter",
                                    ),
                                    className="preview-frame",
                                ),
                                html.Div(
                                    [
                                        html.Span("VISTA PREVIA LPI"),
                                        html.Span("JPG · ORIGINAL ONLINE"),
                                    ],
                                    className="frame-caption",
                                ),
                            ],
                            className="source-block",
                        ),
                        html.Div(
                            [_metadata_row("FOTOGRAMA", DEFAULT_FRAME_ID)],
                            id="metadata",
                            className="metadata source-block",
                        ),
                        html.A(
                            "ABRIR REGISTRO ORIGINAL ↗",
                            id="image-link",
                            href=frame_url(DEFAULT_FRAME_ID),
                            target="_blank",
                            rel="noreferrer",
                            className="source-link source-block",
                        ),
                    ],
                    className="side-panel",
                ),
            ],
            className="atlas-layout",
        ),
        html.Footer(
            [
                html.Span(
                    "FUENTE DE IMAGEN Y METADATOS: LUNAR AND PLANETARY INSTITUTE"
                ),
                html.Span("LAS IMÁGENES PERTENECEN A SUS RESPECTIVOS TITULARES"),
            ],
            className="footbar",
        ),
    ],
    className="app-shell",
)


@app.callback(
    Output("selected-frame", "data"),
    Output("preview", "src"),
    Output("metadata", "children"),
    Output("image-link", "href"),
    Output("status", "children"),
    Input("load-frame", "n_clicks"),
    Input("initial-load", "n_intervals"),
    Input("frame-id", "value"),
    prevent_initial_call=True,
)
def update_frame(_clicks: int, _interval: int, frame_id: str):
    unchanged = (no_update,) * 4
    try:
        frame = fetch_frame(frame_id)
    # RequestException subclasses OSError, so it must be handled first.
    except requests.RequestException as error:
        return *unchanged, f"ERROR DE CONEXIÓN · {error}"
    except (ValueError, OSError, RuntimeError) as error:
        return *unchanged, f"NO SE PUDO CARGAR · {error}"

    image_data = base64.b64encode(frame.image_bytes).decode("ascii")
    status = f"LPI EN LÍNEA · {frame.frame_id} · VISTA PREVIA RECIBIDA"
    return (
        frame.frame_id,
        f"data:image/jpeg;base64,{image_data}",
        metadata_rows(frame),
        frame_url(frame.frame_id),
        status,
    )


def _selected_image(frame_id: str | None) -> GlobeImage | None:
    """Rebuild the selection's texture; the frame itself is in the fetch cache."""
    if not frame_id:
        return None
    try:
        return globe_image(fetch_frame(frame_id))
    except (requests.RequestException, ValueError, OSError):
        return None


@app.callback(
    Output("globe", "figure"),
    Input("selected-frame", "data"),
    Input("hidden-frames", "data"),
    Input("mosaic-count", "data"),
    Input("mission-select", "value"),
)
def render_globe(
    selected_id: str | None,
    hidden: list[str] | None,
    _mosaic_count: int,
    mission: int | None,
):
    tiles = LOADER.progress(mission).tiles.values() if mission else ()
    return make_globe(_selected_image(selected_id), tiles, set(hidden or ()))


@app.callback(
    Output("frame-select", "options"),
    Output("frame-select", "value"),
    Output("frame-select", "disabled"),
    Output("status", "children", allow_duplicate=True),
    Output("mosaic-poll", "disabled"),
    Output("mosaic-count", "data"),
    Output("hidden-frames", "data", allow_duplicate=True),
    Input("mission-select", "value"),
    prevent_initial_call="initial_duplicate",
)
def list_mission_frames(mission: int):
    try:
        frame_ids = fetch_mission_frames(mission)
    except requests.RequestException as error:
        return [], None, True, f"ERROR DE CONEXIÓN · {error}", True, 0, []
    except ValueError as error:
        return [], None, True, f"NO SE PUDO CARGAR · {error}", True, 0, []
    LOADER.start(mission)
    status = f"MISIÓN {mission} · {len(frame_ids)} FOTOGRAMAS"
    return frame_ids, None, False, status, False, 0, []


@app.callback(
    Output("mosaic-status", "children"),
    Output("mosaic-count", "data", allow_duplicate=True),
    Output("mosaic-poll", "disabled", allow_duplicate=True),
    Input("mosaic-poll", "n_intervals"),
    State("mission-select", "value"),
    State("mosaic-count", "data"),
    prevent_initial_call=True,
)
def poll_mosaic(_intervals: int, mission: int | None, rendered: int):
    if not mission:
        return no_update, no_update, True
    progress = LOADER.progress(mission)
    loaded = len(progress.tiles)
    if progress.error:
        return f"MOSAICO NO DISPONIBLE · {progress.error}", no_update, True
    if progress.finished:
        failed = f" · {progress.failed} SIN DATOS" if progress.failed else ""
        count = loaded if loaded != rendered else no_update
        return f"MOSAICO · {loaded} FOTOS EN LA ESFERA{failed}", count, True

    status = f"DESCARGANDO MOSAICO · {loaded}/{progress.total or '…'}"
    count = loaded if loaded - rendered >= MOSAIC_RENDER_STEP else no_update
    return status, count, False


@app.callback(
    Output("hidden-frames", "data"),
    Output("frame-id", "value", allow_duplicate=True),
    Input("globe", "clickData"),
    State("hidden-frames", "data"),
    State("selected-frame", "data"),
    State("mission-select", "value"),
    prevent_initial_call=True,
)
def hide_clicked_image(
    click_data: dict | None,
    hidden: list[str] | None,
    selected_id: str | None,
    mission: int | None,
):
    """Hide the clicked photo and show its details in the side panel."""
    if not click_data or not click_data.get("points"):
        return no_update, no_update
    point = click_data["points"][0]
    if not {"x", "y", "z"} <= point.keys():
        return no_update, no_update

    hidden = list(hidden or ())
    tiles = LOADER.progress(mission).tiles.values() if mission else ()
    images = visible_images(_selected_image(selected_id), tiles, set(hidden))
    clicked = image_at(images, point["x"], point["y"], point["z"])
    if clicked is None:
        return no_update, no_update
    return [*hidden, clicked.frame_id], clicked.frame_id


@app.callback(
    Output("show-hidden", "children"),
    Output("show-hidden", "disabled"),
    Input("hidden-frames", "data"),
)
def describe_hidden(hidden: list[str] | None):
    count = len(hidden or ())
    return f"MOSTRAR OCULTAS ({count})", count == 0


@app.callback(
    Output("hidden-frames", "data", allow_duplicate=True),
    Input("show-hidden", "n_clicks"),
    prevent_initial_call=True,
)
def show_hidden(_clicks: int):
    return []


@app.callback(
    Output("frame-id", "value"),
    Output("hidden-frames", "data", allow_duplicate=True),
    Input("frame-select", "value"),
    State("hidden-frames", "data"),
    prevent_initial_call=True,
)
def select_frame(frame_id: str | None, hidden: list[str] | None):
    """Load the chosen frame and make it visible again if it was hidden."""
    if not frame_id:
        return no_update, no_update
    return frame_id, [value for value in hidden or () if value != frame_id]


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=False)
