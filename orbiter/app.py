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
        hovertext=[f"{frame.frame_id} · {format_coordinates(frame.latitude, frame.longitude)}"],
        hoverinfo="text",
    )


def _camera_eye(latitude: float, longitude: float) -> dict[str, float]:
    x_coordinate, y_coordinate, z_coordinate = _to_cartesian(
        latitude, longitude, CAMERA_DISTANCE
    )
    return {"x": float(x_coordinate), "y": float(y_coordinate), "z": float(z_coordinate)}


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
        _metadata_row("PUNTO PRINCIPAL", format_coordinates(frame.latitude, frame.longitude)),
        _metadata_row("ALTITUD DE LA NAVE", altitude),
        _metadata_row("POSICIÓN DE LA NAVE", spacecraft_position),
        _metadata_row("ACIMUT SOLAR", _degrees(frame.sun_azimuth)),
        _metadata_row(
            "INCIDENCIA / EMISIÓN",
            _degrees(frame.incidence_angle, frame.emission_angle),
        ),
        _metadata_row("ÁNGULO DE FASE", _degrees(frame.phase_angle)),
    ]


app = Dash(__name__)
app.title = "Lunar Orbiter | Atlas"
app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap" rel="stylesheet">
        <style>
            * { box-sizing: border-box; }
            body { margin: 0; background: #101112; color: #e6e3dd; font-family: 'Manrope', sans-serif; }
            button, input { font: inherit; }
            .app-shell { max-width: 1600px; margin: 0 auto; padding: 26px 42px 20px; }
            .topbar { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333537; padding: 0 0 18px; }
            .wordmark { display:flex; gap:13px; align-items:center; }
            .brand-mark { font: 500 12px 'DM Mono',monospace; color:#101112; background:#ff7547; padding:9px 8px; }
            .brand-copy { font: 10px 'DM Mono',monospace; letter-spacing:1px; line-height:1.7; color:#aaa7a0; }
            .top-meta { font: 10px 'DM Mono',monospace; color:#aaa7a0; letter-spacing:.7px; }
            .page-title { display:flex; justify-content:space-between; align-items:end; padding:26px 0 16px; }
            .eyebrow,.section-kicker { font:10px 'DM Mono',monospace; color:#ff8a61; letter-spacing:1.2px; text-transform:uppercase; }
            h1 { margin:5px 0 0; font:600 42px 'Newsreader',serif; letter-spacing:0; }
            .title-note { max-width:310px; color:#aaa7a0; font-size:12px; line-height:1.6; text-align:right; }
            .atlas-layout { display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:26px; min-height:590px; border-top:1px solid #333537; border-bottom:1px solid #333537; }
            .globe-panel { position:relative; min-width:0; min-height:590px; overflow:hidden; background:radial-gradient(ellipse at 50% 53%,#252626 0,#151617 45%,#101112 75%); }
            .globe-label { position:absolute; top:19px; left:20px; z-index:2; font:10px 'DM Mono',monospace; color:#aaa7a0; letter-spacing:.7px; pointer-events:none; }
            .globe-coordinates { position:absolute; right:20px; bottom:17px; z-index:2; font:10px 'DM Mono',monospace; color:#777973; pointer-events:none; }
            .globe-render { width:100%; height:590px; }
            .side-panel { border-left:1px solid #333537; padding:22px 0 22px 24px; display:flex; flex-direction:column; gap:18px; }
            .side-heading { margin:0; font:500 21px 'Newsreader',serif; }
            .control-row { display:flex; gap:8px; }
            .selector-row { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:8px; }
            .side-panel {
                --Dash-Fill-Inverse-Strong:#181a1b; --Dash-Text-Strong:#e6e3dd; --Dash-Text-Weak:#aaa7a0;
                --Dash-Text-Disabled:#5c5e5f; --Dash-Fill-Disabled:#141516; --Dash-Stroke-Strong:#4a4c4d;
                --Dash-Stroke-Weak:#333537; --Dash-Fill-Interactive-Strong:#ff7547; --Dash-Fill-Interactive-Weak:#ff754722;
                --Dash-Fill-Primary-Hover:#ff754722; --Dash-Fill-Primary-Active:#ff754733; --Dash-Text-Primary:#ff8a61;
                --Dash-Shading-Strong:#00000099; --Dash-Shading-Weak:#00000055;
            }
            .selector-row > * { position:relative; min-width:0; }
            .selector-row .dash-dropdown, .dash-dropdown-content { font:11px 'DM Mono',monospace; }
            .selector-row .dash-dropdown-focus-target { width:100% !important; }
            .frame-input { width:100%; min-width:0; background:#181a1b; border:1px solid #4a4c4d; color:#e6e3dd; border-radius:2px; padding:11px 12px; font:12px 'DM Mono',monospace; }
            .load-button { white-space:nowrap; border:0; border-radius:2px; padding:0 13px; color:#141414; background:#ff7547; font-size:11px; font-weight:700; cursor:pointer; }
            .load-button:hover { background:#ff946f; }
            .status-line { min-height:15px; color:#a6a49d; font:9px 'DM Mono',monospace; letter-spacing:.4px; }
            .preview-frame { height:224px; display:flex; align-items:center; justify-content:center; background:#090a0b; border:1px solid #333537; overflow:hidden; }
            .preview-image { display:block; width:100%; height:100%; object-fit:contain; }
            .preview-empty { color:#777973; font:10px 'DM Mono',monospace; }
            .frame-caption { display:flex; justify-content:space-between; color:#aaa7a0; font:9px 'DM Mono',monospace; margin-top:-10px; }
            .metadata { border-top:1px solid #333537; }
            .meta-row { display:flex; justify-content:space-between; gap:10px; border-bottom:1px solid #292b2c; padding:9px 0; }
            .meta-label { color:#777973; font:9px 'DM Mono',monospace; text-transform:uppercase; letter-spacing:.5px; }
            .meta-value { color:#e6e3dd; text-align:right; font:10px 'DM Mono',monospace; }
            .source-link { width:fit-content; color:#ff8a61; font:10px 'DM Mono',monospace; text-decoration:none; border-bottom:1px solid #794b3b; padding-bottom:3px; }
            .source-link:hover { color:#ffc1aa; }
            .footbar { display:flex; justify-content:space-between; gap:20px; padding-top:15px; color:#777973; font:9px 'DM Mono',monospace; }
            @media(max-width:900px) {
                .app-shell { padding:18px 20px; }
                .atlas-layout { grid-template-columns:minmax(0,1fr); }
                .globe-panel { min-height:68vw; }
                .globe-render { height:68vw; min-height:390px; }
                .side-panel { border-left:0; border-top:1px solid #333537; padding:20px 0; display:grid; grid-template-columns:1fr 1fr; align-items:start; }
                .side-panel > .source-block { grid-column:1 / -1; }
                .preview-frame { height:240px; }
            }
            @media(max-width:560px) {
                .app-shell { padding:14px 14px 18px; }
                .top-meta,.title-note { display:none; }
                h1 { font-size:35px; }
                .globe-panel { min-height:360px; }
                .globe-render { height:360px; min-height:360px; }
                .side-panel { display:flex; }
                .preview-frame { height:260px; }
                .footbar { flex-direction:column; gap:7px; }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

app.layout = html.Div(
    [
        dcc.Interval(id="initial-load", interval=500, n_intervals=0, max_intervals=1),
        html.Header(
            [
                html.Div(
                    [
                        html.Div("LO", className="brand-mark"),
                        html.Div(["LUNAR ORBITER", html.Br(), "PHOTO ARCHIVE / FIELD ATLAS"], className="brand-copy"),
                    ],
                    className="wordmark",
                ),
                html.Div("LPI DIGITAL ARCHIVE     ·     LOCAL VIEWER", className="top-meta"),
            ],
            className="topbar",
        ),
        html.Section(
            [
                html.Div(
                    [
                        html.Div("EXPLORACIÓN FOTOGRÁFICA · 1966—1967", className="eyebrow"),
                        html.H1("Atlas orbital lunar"),
                    ]
                ),
                html.Div("Fotogramas históricos del archivo LPI proyectados sobre una esfera interactiva.", className="title-note"),
            ],
            className="page-title",
        ),
        html.Main(
            [
                html.Section(
                    [
                        html.Div("VISTA 3D  /  ARRASTRA PARA ROTAR · RUEDA PARA ACERCAR", className="globe-label"),
                        dcc.Graph(id="globe", figure=make_globe(), className="globe-render", config={"displayModeBar": False, "responsive": True}),
                        html.Div("PROYECCIÓN DEL FOTOGRAMA · COBERTURA ESQUEMÁTICA", className="globe-coordinates"),
                    ],
                    className="globe-panel",
                ),
                html.Aside(
                    [
                        html.Div(
                            [
                                html.Div("ARCHIVO DE IMÁGENES", className="section-kicker"),
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
                                            options=[{"label": f"Lunar Orbiter {number}", "value": number} for number in range(1, MISSIONS_NUM + 1)],
                                            placeholder="MISIÓN",
                                            clearable=False,
                                            searchable=False,
                                        ),
                                        dcc.Dropdown(id="frame-select", options=[], placeholder="FOTOGRAMA", disabled=True),
                                    ],
                                    className="selector-row",
                                ),
                                html.Div(
                                    [
                                        dcc.Input(id="frame-id", value=DEFAULT_FRAME_ID, type="text", className="frame-input", debounce=True, inputMode="numeric"),
                                        html.Button("Cargar ↗", id="load-frame", n_clicks=0, className="load-button"),
                                    ],
                                    className="control-row",
                                ),
                                html.Div("CONECTANDO CON EL ARCHIVO LPI…", id="status", className="status-line"),
                            ],
                            className="source-block",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    html.Img(id="preview", className="preview-image", alt="Vista previa del fotograma Lunar Orbiter"),
                                    className="preview-frame",
                                ),
                                html.Div([html.Span("VISTA PREVIA LPI"), html.Span("JPG · ORIGINAL ONLINE")], className="frame-caption"),
                            ],
                            className="source-block",
                        ),
                        html.Div(
                            [_metadata_row("FOTOGRAMA", DEFAULT_FRAME_ID)],
                            id="metadata",
                            className="metadata source-block",
                        ),
                        html.A("ABRIR REGISTRO ORIGINAL ↗", id="image-link", href=frame_url(DEFAULT_FRAME_ID), target="_blank", rel="noreferrer", className="source-link source-block"),
                    ],
                    className="side-panel",
                ),
            ],
            className="atlas-layout",
        ),
        html.Footer(
            [
                html.Span("FUENTE DE IMAGEN Y METADATOS: LUNAR AND PLANETARY INSTITUTE"),
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