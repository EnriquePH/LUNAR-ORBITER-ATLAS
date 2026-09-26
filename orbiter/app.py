"""Local Dash app for viewing Lunar Orbiter frames on a 3D lunar globe."""

from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
import plotly.graph_objects as go
import requests
from dash import Dash, Input, Output, dcc, html, no_update
from PIL import Image

from orbiter.lpi import OrbiterFrame, fetch_frame, fetch_mission_frames
from orbiter.urls import MISSIONS_NUM, frame_url

DEFAULT_FRAME_ID = "1041"
PATCH_WIDTH_DEGREES = 18.0
TEXTURE_SIZE = (256, 256)
ACCENT = "#ff7547"
BACKGROUND = "#151617"
BASE_SURFACE_VALUE = 112.0
# Lifts the frame patch above the base sphere so it is not z-fighting with it.
PATCH_RADIUS = 1.003
CAMERA_DISTANCE = 1.6
GRAY_SCALE = [[0.0, "#000000"], [1.0, "#ffffff"]]


def _to_cartesian(
    latitude_degrees: np.ndarray | float,
    longitude_degrees: np.ndarray | float,
    radius: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    latitudes = np.radians(latitude_degrees)
    longitudes = np.radians(longitude_degrees)
    return (
        radius * np.cos(latitudes) * np.cos(longitudes),
        radius * np.cos(latitudes) * np.sin(longitudes),
        radius * np.sin(latitudes),
    )


def _thumbnail(image_bytes: bytes) -> Image.Image:
    image = Image.open(BytesIO(image_bytes)).convert("L")
    image.thumbnail(TEXTURE_SIZE, Image.Resampling.LANCZOS)
    return image


def format_coordinates(latitude: float, longitude: float) -> str:
    """Format signed degrees with hemisphere letters (N/S, E/W)."""
    latitude_hemisphere = "N" if latitude >= 0 else "S"
    longitude_hemisphere = "E" if longitude >= 0 else "W"
    return (
        f"{abs(latitude):.2f}° {latitude_hemisphere}  /  "
        f"{abs(longitude):.2f}° {longitude_hemisphere}"
    )


def _base_sphere() -> go.Surface:
    latitudes, longitudes = np.meshgrid(
        np.linspace(-90, 90, 73), np.linspace(-180, 180, 145), indexing="ij"
    )
    x_coordinates, y_coordinates, z_coordinates = _to_cartesian(latitudes, longitudes)
    return go.Surface(
        x=x_coordinates,
        y=y_coordinates,
        z=z_coordinates,
        surfacecolor=np.full(latitudes.shape, BASE_SURFACE_VALUE),
        colorscale=GRAY_SCALE,
        cmin=0,
        cmax=255,
        showscale=False,
        hoverinfo="skip",
        lighting={"ambient": 0.55, "diffuse": 0.7, "specular": 0.05},
    )


def _frame_patch(frame: OrbiterFrame) -> go.Surface:
    """Map the preview onto a lat/lon patch centred on the principal point.

    The patch is schematic: its angular size is fixed, not derived from the
    camera geometry, and longitudes widen with latitude so it keeps its aspect.
    """
    image = np.asarray(_thumbnail(frame.image_bytes), dtype=np.float32)
    height, width = image.shape
    patch_height = PATCH_WIDTH_DEGREES * height / width
    longitude_span = PATCH_WIDTH_DEGREES / max(np.cos(np.radians(frame.latitude)), 0.2)
    # Image rows run north to south; columns run west to east.
    latitudes = np.clip(
        np.linspace(
            frame.latitude + patch_height / 2, frame.latitude - patch_height / 2, height
        ),
        -90,
        90,
    )
    longitudes = np.linspace(
        frame.longitude - longitude_span / 2,
        frame.longitude + longitude_span / 2,
        width,
    )
    latitude_grid, longitude_grid = np.meshgrid(latitudes, longitudes, indexing="ij")
    x_coordinates, y_coordinates, z_coordinates = _to_cartesian(
        latitude_grid, longitude_grid, PATCH_RADIUS
    )
    return go.Surface(
        x=x_coordinates,
        y=y_coordinates,
        z=z_coordinates,
        surfacecolor=image,
        colorscale=GRAY_SCALE,
        cmin=0,
        cmax=255,
        showscale=False,
        hoverinfo="skip",
        lighting={"ambient": 0.8, "diffuse": 0.4, "specular": 0.0},
    )


def _frame_marker(frame: OrbiterFrame) -> go.Scatter3d:
    x_coordinate, y_coordinate, z_coordinate = _to_cartesian(
        frame.latitude, frame.longitude, 1.02
    )
    return go.Scatter3d(
        x=[x_coordinate],
        y=[y_coordinate],
        z=[z_coordinate],
        mode="markers+text",
        marker={"size": 4, "color": ACCENT},
        text=[frame.frame_id],
        textposition="top center",
        textfont={"color": "#ff9c79", "family": "DM Mono, monospace", "size": 11},
        hovertext=[
            f"{frame.frame_id} · {format_coordinates(frame.latitude, frame.longitude)}"
        ],
        hoverinfo="text",
    )


def _camera_eye(latitude: float, longitude: float) -> dict[str, float]:
    x_coordinate, y_coordinate, z_coordinate = _to_cartesian(
        latitude, longitude, CAMERA_DISTANCE
    )
    return {
        "x": float(x_coordinate),
        "y": float(y_coordinate),
        "z": float(z_coordinate),
    }


def make_globe(frame: OrbiterFrame | None = None) -> go.Figure:
    """Build an interactive globe, centred on the frame when one is given."""
    traces: list[go.Surface | go.Scatter3d] = [_base_sphere()]
    if frame is None:
        eye = _camera_eye(22, 35)
    else:
        traces += [_frame_patch(frame), _frame_marker(frame)]
        eye = _camera_eye(frame.latitude, frame.longitude)

    hidden_axis = {"visible": False, "range": [-1.1, 1.1]}
    figure = go.Figure(traces)
    figure.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        scene={
            "xaxis": hidden_axis,
            "yaxis": hidden_axis,
            "zaxis": hidden_axis,
            "aspectmode": "cube",
            "bgcolor": "rgba(0,0,0,0)",
            "camera": {"eye": eye, "up": {"x": 0, "y": 0, "z": 1}},
        },
    )
    return figure


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
                            "VISTA 3D  /  ARRASTRA PARA ROTAR · RUEDA PARA ACERCAR",
                            className="globe-label",
                        ),
                        dcc.Graph(
                            id="globe",
                            figure=make_globe(),
                            className="globe-render",
                            config={"displayModeBar": False, "responsive": True},
                        ),
                        html.Div(
                            "PROYECCIÓN DEL FOTOGRAMA · COBERTURA ESQUEMÁTICA",
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
    Output("globe", "figure"),
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
        make_globe(frame),
        f"data:image/jpeg;base64,{image_data}",
        metadata_rows(frame),
        frame_url(frame.frame_id),
        status,
    )


@app.callback(
    Output("frame-select", "options"),
    Output("frame-select", "value"),
    Output("frame-select", "disabled"),
    Output("status", "children", allow_duplicate=True),
    Input("mission-select", "value"),
    prevent_initial_call=True,
)
def list_mission_frames(mission: int):
    try:
        frame_ids = fetch_mission_frames(mission)
    except requests.RequestException as error:
        return [], None, True, f"ERROR DE CONEXIÓN · {error}"
    except ValueError as error:
        return [], None, True, f"NO SE PUDO CARGAR · {error}"
    status = f"MISIÓN {mission} · {len(frame_ids)} FOTOGRAMAS"
    return frame_ids, None, False, status


@app.callback(
    Output("frame-id", "value"),
    Input("frame-select", "value"),
    prevent_initial_call=True,
)
def select_frame(frame_id: str | None):
    return frame_id or no_update


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=False)
