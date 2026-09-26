"""Local Dash app for viewing Lunar Orbiter frames on a 3D lunar globe."""

from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
import requests
from dash import Dash, Input, Output, State, dcc, html, no_update
from matplotlib import cm
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image

from orbiter.lpi import OrbiterFrame, fetch_frame
from orbiter.urls import frame_url

DEFAULT_FRAME_ID = "1041"
PATCH_WIDTH_DEGREES = 18.0
TEXTURE_SIZE = (144, 144)
ACCENT = "#ff7547"


def _sphere_coordinates() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    latitude_values = np.linspace(-90, 90, 73)
    longitude_values = np.linspace(-180, 180, 145)
    latitudes = np.radians(latitude_values)
    longitudes = np.radians(longitude_values)
    latitude_grid, longitude_grid = np.meshgrid(latitudes, longitudes, indexing="ij")
    x_coordinates = np.cos(latitude_grid) * np.cos(longitude_grid)
    y_coordinates = np.cos(latitude_grid) * np.sin(longitude_grid)
    z_coordinates = np.sin(latitude_grid)
    return x_coordinates, y_coordinates, z_coordinates, latitude_values, longitude_values


def _thumbnail(image_bytes: bytes) -> Image.Image:
    image = Image.open(BytesIO(image_bytes)).convert("L")
    image.thumbnail(TEXTURE_SIZE, Image.Resampling.LANCZOS)
    return image


def _frame_texture(frame: OrbiterFrame | dict) -> np.ndarray:
    if isinstance(frame, OrbiterFrame):
        image = _thumbnail(frame.image_bytes)
    else:
        image = Image.open(BytesIO(base64.b64decode(frame["texture"])))
    return np.asarray(image, dtype=np.float32)


def format_coordinates(latitude: float, longitude: float) -> str:
    """Format signed degrees with hemisphere letters (N/S, E/W)."""
    latitude_hemisphere = "N" if latitude >= 0 else "S"
    longitude_hemisphere = "E" if longitude >= 0 else "W"
    return (
        f"{abs(latitude):.2f}° {latitude_hemisphere}  /  "
        f"{abs(longitude):.2f}° {longitude_hemisphere}"
    )


def make_globe(
    frame: OrbiterFrame | dict | None = None,
    azimuth: float = 35,
    elevation: float = 22,
) -> str:
    """Render the sphere to a PNG and return it as a browser-ready data URL."""
    x_coordinates, y_coordinates, z_coordinates, latitude_values, longitude_values = _sphere_coordinates()
    surface = np.full(x_coordinates.shape, 112.0, dtype=np.float32)
    frame_latitude = frame_longitude = None
    frame_id = ""

    if frame is not None:
        image = _frame_texture(frame)
        height, width = image.shape
        frame_latitude = float(frame.latitude if isinstance(frame, OrbiterFrame) else frame["latitude"])
        frame_longitude = float(frame.longitude if isinstance(frame, OrbiterFrame) else frame["longitude"])
        frame_id = frame.frame_id if isinstance(frame, OrbiterFrame) else str(frame["frame_id"])
        latitudes = latitude_values[:, None]
        longitudes = longitude_values[None, :]
        delta_longitude = (longitudes - frame_longitude + 180) % 360 - 180
        patch_height = PATCH_WIDTH_DEGREES * height / width
        row_start = frame_latitude + patch_height / 2
        row_fraction = (row_start - latitudes) / patch_height
        column_fraction = delta_longitude / PATCH_WIDTH_DEGREES + 0.5
        mask = (
            (row_fraction >= 0)
            & (row_fraction <= 1)
            & (column_fraction >= 0)
            & (column_fraction <= 1)
        )
        rows = np.clip((row_fraction * (height - 1)).astype(int), 0, height - 1)
        columns = np.clip((column_fraction * (width - 1)).astype(int), 0, width - 1)
        sampled = image[rows, columns]
        surface[mask] = sampled[mask]

    figure = Figure(figsize=(7, 6), dpi=115, facecolor="#151617")
    FigureCanvasAgg(figure)
    axes = figure.add_subplot(111, projection="3d")
    axes.set_facecolor("#151617")
    axes.plot_surface(
        x_coordinates,
        y_coordinates,
        z_coordinates,
        facecolors=cm.gray(np.clip(surface / 255, 0, 1)),
        rstride=1,
        cstride=1,
        linewidth=0,
        antialiased=False,
        shade=True,
    )
    if frame_latitude is not None and frame_longitude is not None:
        latitude_radians = np.radians(frame_latitude)
        longitude_radians = np.radians(frame_longitude)
        axes.scatter(
            [1.01 * np.cos(latitude_radians) * np.cos(longitude_radians)],
            [1.01 * np.cos(latitude_radians) * np.sin(longitude_radians)],
            [1.01 * np.sin(latitude_radians)],
            color=ACCENT,
            s=16,
            depthshade=False,
        )
        axes.text(
            1.07 * np.cos(latitude_radians) * np.cos(longitude_radians),
            1.07 * np.cos(latitude_radians) * np.sin(longitude_radians),
            1.07 * np.sin(latitude_radians),
            frame_id,
            color="#ff9c79",
            fontsize=8,
        )
    axes.set(xlim=(-1.08, 1.08), ylim=(-1.08, 1.08), zlim=(-1.08, 1.08))
    axes.set_box_aspect((1, 1, 1))
    axes.view_init(elev=elevation, azim=azimuth)
    axes.set_axis_off()
    figure.subplots_adjust(left=0, right=1, top=1, bottom=0)

    output = BytesIO()
    figure.savefig(output, format="png", facecolor=figure.get_facecolor(), dpi=115)
    encoded_image = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded_image}"


def _metadata_row(label: str, value_id: str, value: str = "—") -> html.Div:
    return html.Div(
        [
            html.Span(label, className="meta-label"),
            html.Span(value, id=value_id, className="meta-value"),
        ],
        className="meta-row",
    )


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
            .globe-render { display:block; width:100%; height:590px; object-fit:contain; }
            .side-panel { border-left:1px solid #333537; padding:22px 0 22px 24px; display:flex; flex-direction:column; gap:18px; }
            .side-heading { margin:0; font:500 21px 'Newsreader',serif; }
            .control-row { display:flex; gap:8px; }
            .rotation-grid { display:grid; gap:14px; padding-top:3px; }
            .rotation-control { display:grid; gap:7px; }
            .rotation-label { display:flex; justify-content:space-between; color:#aaa7a0; font:9px 'DM Mono',monospace; letter-spacing:.5px; }
            .rotation-control .rc-slider-track { background:#ff7547; }
            .rotation-control .rc-slider-rail { background:#3d3f40; }
            .rotation-control .rc-slider-handle { border-color:#ff7547; background:#151617; box-shadow:none; }
            .rotation-control .rc-slider-handle:hover,.rotation-control .rc-slider-handle:active { border-color:#ff9c79; box-shadow:0 0 0 4px #ff754722; }
            .rotation-control .rc-slider-mark-text { color:#777973; font:8px 'DM Mono',monospace; }
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
        dcc.Store(id="frame-data"),
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
                        html.Div("VISTA 3D  /  AJUSTA AZIMUT Y ELEVACIÓN", className="globe-label"),
                        html.Img(id="globe-image", src=make_globe(), className="globe-render", alt="Esfera lunar 3D con la zona cubierta por el fotograma seleccionado"),
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
                                        html.Span("AZIMUT", className="rotation-label"),
                                        dcc.Slider(
                                            id="rotation-azimuth",
                                            min=-180,
                                            max=180,
                                            step=5,
                                            value=35,
                                            marks={-180: "-180", 0: "0", 180: "180"},
                                            tooltip={"placement": "bottom", "always_visible": False},
                                        ),
                                    ],
                                    className="rotation-control",
                                ),
                                html.Div(
                                    [
                                        html.Span("ELEVACIÓN", className="rotation-label"),
                                        dcc.Slider(
                                            id="rotation-elevation",
                                            min=-75,
                                            max=75,
                                            step=5,
                                            value=22,
                                            marks={-75: "-75", 0: "0", 75: "75"},
                                            tooltip={"placement": "bottom", "always_visible": False},
                                        ),
                                    ],
                                    className="rotation-control",
                                ),
                            ],
                            className="rotation-grid source-block",
                        ),
                        html.Div(
                            [
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
                            [
                                _metadata_row("MISIÓN", "mission-value"),
                                _metadata_row("PUNTO PRINCIPAL", "center-value"),
                                _metadata_row("FOTOGRAMA", "frame-value", DEFAULT_FRAME_ID),
                            ],
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
    Output("globe-image", "src"),
    Output("preview", "src"),
    Output("mission-value", "children"),
    Output("center-value", "children"),
    Output("frame-value", "children"),
    Output("image-link", "href"),
    Output("status", "children"),
    Output("frame-data", "data"),
    Input("load-frame", "n_clicks"),
    Input("initial-load", "n_intervals"),
    State("frame-id", "value"),
    prevent_initial_call=True,
)
def update_frame(_clicks: int, _interval: int, frame_id: str):
    unchanged = (no_update,) * 6
    try:
        frame = fetch_frame(frame_id)
    # RequestException subclasses OSError, so it must be handled first.
    except requests.RequestException as error:
        return *unchanged, f"ERROR DE CONEXIÓN · {error}", no_update
    except (ValueError, OSError, RuntimeError) as error:
        return *unchanged, f"NO SE PUDO CARGAR · {error}", no_update

    image_data = base64.b64encode(frame.image_bytes).decode("ascii")
    image_src = f"data:image/jpeg;base64,{image_data}"
    thumbnail = _thumbnail(frame.image_bytes)
    thumbnail_buffer = BytesIO()
    thumbnail.save(thumbnail_buffer, format="PNG")
    render_data = {
        "frame_id": frame.frame_id,
        "mission": frame.mission,
        "latitude": frame.latitude,
        "longitude": frame.longitude,
        "texture": base64.b64encode(thumbnail_buffer.getvalue()).decode("ascii"),
    }
    page_url = frame_url(frame.frame_id)
    center = format_coordinates(frame.latitude, frame.longitude)
    status = f"LPI EN LÍNEA · {frame.frame_id} · VISTA PREVIA RECIBIDA"
    return make_globe(frame), image_src, frame.mission, center, frame.frame_id, page_url, status, render_data


@app.callback(
    Output("globe-image", "src", allow_duplicate=True),
    Input("rotation-azimuth", "value"),
    Input("rotation-elevation", "value"),
    State("frame-data", "data"),
    prevent_initial_call=True,
)
def rotate_globe(azimuth: float, elevation: float, frame_data: dict | None):
    return make_globe(frame_data, azimuth, elevation)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=False)