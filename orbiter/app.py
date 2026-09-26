"""Local Dash app for viewing Lunar Orbiter frames on a 3D lunar globe."""

from __future__ import annotations

import base64
import random
from io import BytesIO
from urllib.parse import parse_qs

import numpy as np
import requests
from dash import Dash, Input, Output, Patch, State, dcc, html, no_update
from PIL import Image

from orbiter.catalog import MissionLoader, TileStore, default_cache_dir
from orbiter.config import load_config
from orbiter.export import footprints_geojson, mission_csv
from orbiter.globe import (
    EMISSION_TOLERANCE_DEGREES,
    HIGH_ALTITUDE_KM,
    FrameGeometry,
    GlobeImage,
    camera_distance,
    camera_of,
    focus_camera,
    format_coordinates,
    frame_geometry,
    make_globe,
)
from orbiter.i18n import LANGUAGES, normalize_language, t
from orbiter.lpi import (
    FrameMetadata,
    LpiError,
    OrbiterFrame,
    fetch_frame,
    fetch_mission_frames,
)
from orbiter.reference import moon_tab, program_tab
from orbiter.urls import MISSIONS_NUM, frame_url

DEFAULT_FRAME_ID = "1041"
PROJECT_PAGE_URL = "https://enriqueph.github.io/LUNAR-ORBITER-ATLAS/"
REPOSITORY_URL = "https://github.com/EnriquePH/LUNAR-ORBITER-ATLAS"
DEFAULT_MISSION = 1
TEXTURE_SIZE = (256, 256)
# Re-render the globe after this many new tiles while a mission is loading.
MOSAIC_RENDER_STEP = 25

CONFIG = load_config()
LOADER = MissionLoader(TileStore(default_cache_dir()))


def _thumbnail(image_bytes: bytes) -> Image.Image:
    image = Image.open(BytesIO(image_bytes)).convert("L")
    image.thumbnail(TEXTURE_SIZE, Image.Resampling.LANCZOS)
    return image


def globe_image(frame: OrbiterFrame) -> GlobeImage:
    """Build the globe image of the selected frame.

    The texture is the LPI preview reduced to at most ``TEXTURE_SIZE`` pixels:
    sharper than the mosaic tiles, but not the full preview, which the side
    panel shows separately from ``frame.image_bytes``.
    """
    return GlobeImage(
        frame_id=frame.frame_id,
        latitude=frame.latitude,
        longitude=frame.longitude,
        altitude_km=frame.spacecraft_altitude_km,
        texture=np.asarray(_thumbnail(frame.image_bytes), dtype=np.uint8),
        spacecraft_latitude=frame.spacecraft_latitude,
        spacecraft_longitude=frame.spacecraft_longitude,
        emission_angle=frame.emission_angle,
        camera=camera_of(frame.image_url),
    )


def describe_error(lang: str, error: Exception) -> str:
    """Translate LPI errors; other errors keep their own (technical) message."""
    if isinstance(error, LpiError):
        return t(lang, f"error_{error.key}", **error.params)
    return str(error)


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


def _footprint(geometry: FrameGeometry, lang: str) -> str:
    key = "footprint_projected" if geometry.projected else "footprint_approximate"
    return t(
        lang, key, width=f"{geometry.width_km:.1f}", height=f"{geometry.height_km:.1f}"
    )


def _emission_check(
    frame: OrbiterFrame, geometry: FrameGeometry, lang: str
) -> tuple[str, bool]:
    """Format the LPI and computed emission angles; flag a rejected projection."""
    lpi, computed = frame.emission_angle, geometry.implied_emission
    if lpi is None or computed is None:
        return "—", False
    delta = abs(computed - lpi)
    rejected = delta > EMISSION_TOLERANCE_DEGREES
    text = t(
        lang,
        "emission_check_rejected" if rejected else "emission_check",
        lpi=_degrees(lpi),
        computed=_degrees(computed),
        delta=_degrees(delta),
        tolerance=_degrees(EMISSION_TOLERANCE_DEGREES),
    )
    return text, rejected


def metadata_rows(
    frame: OrbiterFrame, lang: str = "es", image: GlobeImage | None = None
) -> list[html.Div]:
    """Build the side-panel rows; fields missing from the LPI page show "—".

    Args:
        frame: The frame from the LPI.
        lang: Interface language.
        image: The frame's globe image, if already built; otherwise it is built
            from ``frame`` to measure the footprint and check the geometry.
    """
    image = image or globe_image(frame)
    geometry = frame_geometry(image)
    emission_check, rejected = _emission_check(frame, geometry, lang)
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
        _metadata_row(t(lang, "meta_mission"), frame.mission),
        _metadata_row(t(lang, "meta_frame"), frame.frame_id),
        _metadata_row(
            t(lang, "meta_principal_point"),
            format_coordinates(frame.latitude, frame.longitude),
        ),
        _metadata_row(t(lang, "meta_altitude"), altitude),
        _metadata_row(t(lang, "meta_spacecraft_position"), spacecraft_position),
        _metadata_row(t(lang, "meta_sun_azimuth"), _degrees(frame.sun_azimuth)),
        _metadata_row(
            t(lang, "meta_incidence_emission"),
            _degrees(frame.incidence_angle, frame.emission_angle),
        ),
        _metadata_row(t(lang, "meta_phase"), _degrees(frame.phase_angle)),
        _metadata_row(t(lang, "meta_camera"), t(lang, f"camera_{image.camera}")),
        _metadata_row(t(lang, "meta_footprint"), _footprint(geometry, lang)),
        _metadata_row(t(lang, "meta_emission_check"), emission_check),
        *(
            [html.P(t(lang, "note_emission_rejected"), className="meta-note")]
            if rejected
            else []
        ),
        *(
            [html.P(t(lang, "note_high_altitude"), className="meta-note")]
            if frame.spacecraft_altitude_km is not None
            and frame.spacecraft_altitude_km > HIGH_ALTITUDE_KM
            else []
        ),
    ]


# DM Mono is the only typeface in the app (text, headings and the globe).
FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&display=swap"
)

# Pages are built by a callback, so their component IDs are not in the
# initial layout; the callbacks below still validate against serve_layout().
app = Dash(
    __name__, external_stylesheets=[FONTS_URL], suppress_callback_exceptions=True
)
app.title = "Lunar Orbiter Atlas"
# Dash's default page plus PNG and touch icons (favicon.ico is automatic).
app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        <link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
        <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
        {%css%}
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


def language_from_search(search: str | None) -> str:
    """Read ``?lang=`` from a URL query string, falling back to the config."""
    requested = parse_qs((search or "").lstrip("?")).get("lang", [None])[0]
    return normalize_language(requested, CONFIG.language)


def _language_switch(lang: str) -> html.Nav:
    return html.Nav(
        [
            html.A(
                code.upper(),
                href=f"?lang={code}",
                className="lang-link lang-link--active"
                if code == lang
                else "lang-link",
                lang=code,
            )
            for code in LANGUAGES
        ],
        className="lang-switch",
        **{"aria-label": "Language / Idioma"},
    )


def _atlas(lang: str) -> html.Main:
    return html.Main(
        [
            html.Section(
                [
                    html.Div(t(lang, "globe_label"), className="globe-label"),
                    dcc.Checklist(
                        id="show-labels",
                        options=[{"label": t(lang, "labels_toggle"), "value": "on"}],
                        value=["on"],
                        persistence=True,
                        persistence_type="local",
                        className="labels-toggle",
                    ),
                    dcc.Graph(
                        id="globe",
                        figure=make_globe(),
                        className="globe-render",
                        config={"displayModeBar": False, "responsive": True},
                    ),
                    html.Div(
                        [
                            html.Span(className="legend-swatch"),
                            t(lang, "legend_high_altitude", km=int(HIGH_ALTITUDE_KM)),
                        ],
                        className="globe-legend",
                    ),
                    html.Div(t(lang, "globe_note"), className="globe-coordinates"),
                ],
                className="globe-panel",
            ),
            html.Aside(
                [
                    html.Div(
                        [
                            html.Div(
                                t(lang, "archive_kicker"), className="section-kicker"
                            ),
                            html.H2(t(lang, "frame_heading"), className="side-heading"),
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
                                        placeholder=t(lang, "mission_placeholder"),
                                        clearable=False,
                                        searchable=False,
                                    ),
                                    dcc.Dropdown(
                                        id="frame-select",
                                        options=[],
                                        placeholder=t(lang, "frame_placeholder"),
                                        disabled=True,
                                    ),
                                ],
                                className="selector-row",
                            ),
                            html.Div(
                                t(lang, "mosaic_preparing"),
                                id="mosaic-status",
                                className="status-line mosaic-status",
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        t(lang, "export_label"),
                                        className="export-label",
                                    ),
                                    html.Button(
                                        "CSV",
                                        id="export-csv",
                                        n_clicks=0,
                                        title=t(lang, "export_csv_title"),
                                        className="export-button",
                                    ),
                                    html.Button(
                                        "GeoJSON",
                                        id="export-geojson",
                                        n_clicks=0,
                                        title=t(lang, "export_geojson_title"),
                                        className="export-button",
                                    ),
                                    dcc.Download(id="download-csv"),
                                    dcc.Download(id="download-geojson"),
                                ],
                                className="export-row",
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
                                        t(lang, "load_button"),
                                        id="load-frame",
                                        n_clicks=0,
                                        className="load-button",
                                    ),
                                    html.Button(
                                        t(lang, "random_button"),
                                        id="random-frame",
                                        n_clicks=0,
                                        disabled=True,
                                        title=t(lang, "random_title"),
                                        className="random-button",
                                    ),
                                ],
                                className="control-row",
                            ),
                            html.Div(
                                t(lang, "connecting"),
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
                                    alt=t(lang, "preview_alt"),
                                ),
                                className="preview-frame",
                            ),
                            html.Div(
                                [
                                    html.Span(t(lang, "preview_caption")),
                                    html.Span(t(lang, "preview_format")),
                                ],
                                className="frame-caption",
                            ),
                        ],
                        className="source-block",
                    ),
                    html.Div(
                        [_metadata_row(t(lang, "meta_frame"), DEFAULT_FRAME_ID)],
                        id="metadata",
                        className="metadata source-block",
                    ),
                    html.A(
                        t(lang, "open_record"),
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
    )


def serve_layout(lang: str) -> html.Div:
    """Build the page in one language; switching reloads with ``?lang=``."""
    tab_classes = {"className": "tab", "selected_className": "tab--selected"}
    return html.Div(
        [
            dcc.Store(id="lang", data=lang),
            dcc.Interval(
                id="initial-load", interval=500, n_intervals=0, max_intervals=1
            ),
            dcc.Interval(id="mosaic-poll", interval=1000, disabled=True),
            dcc.Store(id="selected-frame"),
            # The user's current view, the photo last clicked on the globe and
            # the selection the view last turned to (see render_globe).
            dcc.Store(id="globe-camera"),
            dcc.Store(id="clicked-frame"),
            dcc.Store(id="focused-frame"),
            dcc.Store(id="mosaic-count", data=0),
            html.Header(
                [
                    html.A(
                        [
                            html.Img(
                                src=app.get_asset_url("icon.png"),
                                alt="",
                                className="brand-logo",
                            ),
                            html.Div(
                                ["LUNAR ORBITER", html.Br(), t(lang, "brand_subtitle")],
                                className="brand-copy",
                            ),
                        ],
                        href=PROJECT_PAGE_URL,
                        target="_blank",
                        rel="noreferrer",
                        title=t(lang, "project_page_title"),
                        className="wordmark",
                    ),
                    html.Div(
                        [
                            html.Div(t(lang, "top_meta"), className="top-meta"),
                            html.A(
                                t(lang, "repository_link"),
                                href=REPOSITORY_URL,
                                target="_blank",
                                rel="noreferrer",
                                title=t(lang, "repository_title"),
                                className="repo-link",
                            ),
                            _language_switch(lang),
                        ],
                        className="topbar-end",
                    ),
                ],
                className="topbar",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div(t(lang, "eyebrow"), className="eyebrow"),
                            html.H1(t(lang, "title")),
                        ]
                    ),
                    html.Div(t(lang, "title_note"), className="title-note"),
                ],
                className="page-title",
            ),
            dcc.Tabs(
                id="tabs",
                value="atlas",
                className="tabs",
                children=[
                    dcc.Tab(
                        label=t(lang, "tab_atlas"),
                        value="atlas",
                        children=_atlas(lang),
                        **tab_classes,
                    ),
                    dcc.Tab(
                        label=t(lang, "tab_moon"),
                        value="moon",
                        children=moon_tab(lang),
                        **tab_classes,
                    ),
                    dcc.Tab(
                        label=t(lang, "tab_program"),
                        value="program",
                        children=program_tab(lang),
                        **tab_classes,
                    ),
                ],
            ),
            html.Footer(
                [
                    html.Span(t(lang, "footer_source")),
                    html.Span(t(lang, "footer_rights")),
                ],
                className="footbar",
            ),
        ],
        className="app-shell",
        lang=lang,
    )


# refresh=False: restoring the saved language rewrites ?lang= without a reload.
ROOT = [
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="lang-saved"),
    html.Div(id="page"),
]
app.layout = html.Div(ROOT)
app.validation_layout = html.Div([*ROOT, serve_layout(CONFIG.language)])


LANGUAGE_STORAGE_KEY = "lunar-orbiter-lang"

# Browser-side language memory. Storage can be unavailable (private windows,
# blocked site data), so every access is guarded and the app works without it.
app.clientside_callback(
    f"""
    function (lang) {{
        document.documentElement.lang = lang;
        try {{
            if (new URLSearchParams(window.location.search).has("lang")) {{
                window.localStorage.setItem("{LANGUAGE_STORAGE_KEY}", lang);
            }}
        }} catch (error) {{}}
        return lang;
    }}
    """,
    Output("lang-saved", "data"),
    Input("lang", "data"),
)
app.clientside_callback(
    f"""
    function (search) {{
        const params = new URLSearchParams(search || "");
        if (params.has("lang")) {{
            return window.dash_clientside.no_update;
        }}
        let saved = null;
        try {{
            saved = window.localStorage.getItem("{LANGUAGE_STORAGE_KEY}");
        }} catch (error) {{}}
        if (!{list(LANGUAGES)!r}.includes(saved)) {{
            return window.dash_clientside.no_update;
        }}
        params.set("lang", saved);
        return "?" + params.toString();
    }}
    """,
    Output("url", "search"),
    Input("url", "search"),
)


@app.callback(Output("page", "children"), Input("url", "search"))
def render_page(search: str | None):
    """Build the page in the language of the URL's ``?lang=``."""
    return serve_layout(language_from_search(search))


@app.callback(
    Output("selected-frame", "data"),
    Output("preview", "src"),
    Output("metadata", "children"),
    Output("image-link", "href"),
    Output("status", "children"),
    Input("load-frame", "n_clicks"),
    Input("initial-load", "n_intervals"),
    Input("frame-id", "value"),
    State("lang", "data"),
    prevent_initial_call=True,
)
def update_frame(_clicks: int, _interval: int, frame_id: str, lang: str = "es"):
    """Load a frame into the side panel and make it the globe's selection.

    Returns the selected ID, preview data URL, metadata rows, LPI link and
    status line; on failure only the status changes.
    """
    unchanged = (no_update,) * 4
    try:
        frame = fetch_frame(frame_id)
    # RequestException subclasses OSError, so it must be handled first.
    except requests.RequestException as error:
        return *unchanged, t(lang, "status_connection_error", error=error)
    except (ValueError, OSError, RuntimeError) as error:
        return *unchanged, t(
            lang, "status_load_error", error=describe_error(lang, error)
        )

    image_data = base64.b64encode(frame.image_bytes).decode("ascii")
    status = t(lang, "status_frame_loaded", frame_id=frame.frame_id)
    return (
        frame.frame_id,
        f"data:image/jpeg;base64,{image_data}",
        metadata_rows(frame, lang),
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
    Output("focused-frame", "data"),
    Output("globe-camera", "data", allow_duplicate=True),
    Output("clicked-frame", "data", allow_duplicate=True),
    Input("selected-frame", "data"),
    Input("mosaic-count", "data"),
    Input("mission-select", "value"),
    Input("show-labels", "value"),
    State("globe-camera", "data"),
    State("clicked-frame", "data"),
    State("focused-frame", "data"),
    prevent_initial_call="initial_duplicate",
)
def render_globe(
    selected_id: str | None,
    _mosaic_count: int,
    mission: int | None,
    show_labels: list[str] | None = ("on",),
    current_camera: dict | None = None,
    clicked_id: str | None = None,
    focused_id: str | None = None,
):
    """Redraw the globe with the mission's loaded tiles and the selection.

    The view stays where the user left it. Only a new selection that did not
    come from a click on the globe (selector, typed ID, random) turns the view
    to face the photo, keeping the zoom.

    Args:
        selected_id: The frame in the side panel.
        _mosaic_count: Tiles rendered so far; changes trigger a redraw.
        mission: The selected mission.
        show_labels: The labels checklist value; IDs are drawn when it
            contains ``"on"``.
        current_camera: The user's ``scene.camera`` (from ``globe-camera``).
        clicked_id: The photo last clicked on the globe.
        focused_id: The selection the view last turned to.

    Returns:
        The figure, the selection now faced, the camera used, and the cleared
        click marker (``None``) once a new selection has been handled.
    """
    tiles = LOADER.progress(mission).tiles.values() if mission else ()
    selected = _selected_image(selected_id)
    camera, clicked = current_camera, no_update
    if selected is not None and selected_id != focused_id:
        if selected_id != clicked_id and current_camera is not None:
            distance = camera_distance(current_camera)
            camera = focus_camera(
                selected.latitude,
                selected.longitude,
                *([distance] if distance else []),
            )
        clicked = None
    figure = make_globe(
        selected, tiles, show_labels="on" in (show_labels or ()), camera=camera
    )
    return figure, selected_id, figure.layout.scene.camera.to_plotly_json(), clicked


@app.callback(
    Output("globe-camera", "data"),
    Output("globe", "figure", allow_duplicate=True),
    Input("globe", "relayoutData"),
    prevent_initial_call=True,
)
def remember_camera(relayout: dict | None):
    """Keep the view the user rotated or zoomed to.

    The camera is stored for :func:`render_globe` and patched into the figure
    itself: switching tabs unmounts the graph, which comes back from its
    ``figure`` and would otherwise reopen at an old view.
    """
    camera = (relayout or {}).get("scene.camera")
    if not camera_distance(camera):
        return no_update, no_update
    figure = Patch()
    figure["layout"]["scene"]["camera"] = camera
    return camera, figure


@app.callback(
    Output("frame-select", "options"),
    Output("frame-select", "value"),
    Output("frame-select", "disabled"),
    Output("random-frame", "disabled"),
    Output("status", "children", allow_duplicate=True),
    Output("mosaic-poll", "disabled"),
    Output("mosaic-count", "data"),
    Input("mission-select", "value"),
    State("lang", "data"),
    prevent_initial_call="initial_duplicate",
)
def list_mission_frames(mission: int, lang: str = "es"):
    """Fill the frame selector and start downloading the mission's mosaic."""
    try:
        frame_ids = fetch_mission_frames(mission)
    except requests.RequestException as error:
        status = t(lang, "status_connection_error", error=error)
        return [], None, True, True, status, True, 0
    except ValueError as error:
        status = t(lang, "status_load_error", error=describe_error(lang, error))
        return [], None, True, True, status, True, 0
    LOADER.start(mission)
    status = t(lang, "status_mission_frames", mission=mission, count=len(frame_ids))
    return frame_ids, None, False, False, status, False, 0


@app.callback(
    Output("mosaic-status", "children"),
    Output("mosaic-count", "data", allow_duplicate=True),
    Output("mosaic-poll", "disabled", allow_duplicate=True),
    Input("mosaic-poll", "n_intervals"),
    State("mission-select", "value"),
    State("mosaic-count", "data"),
    State("lang", "data"),
    prevent_initial_call=True,
)
def poll_mosaic(_intervals: int, mission: int | None, rendered: int, lang="es"):
    """Report download progress and trigger redraws as tiles arrive.

    Redraws every ``MOSAIC_RENDER_STEP`` tiles and once at the end, then stops
    polling.
    """
    if not mission:
        return no_update, no_update, True
    progress = LOADER.progress(mission)
    loaded = len(progress.tiles)
    if progress.error:
        error = describe_error(lang, progress.error)
        return t(lang, "mosaic_unavailable", error=error), no_update, True
    if progress.finished:
        failed = (
            t(lang, "mosaic_failed", count=progress.failed) if progress.failed else ""
        )
        count = loaded if loaded != rendered else no_update
        return t(lang, "mosaic_done", count=loaded, failed=failed), count, True

    status = t(lang, "mosaic_loading", loaded=loaded, total=progress.total or "…")
    count = loaded if loaded - rendered >= MOSAIC_RENDER_STEP else no_update
    return status, count, False


def _clicked_frame_id(point: dict) -> str | None:
    """Frame ID carried by a clicked mosaic vertex, as its hover label shows it."""
    frame = point.get("customdata")
    if isinstance(frame, list):
        frame = frame[0] if frame else None
    try:
        return str(int(frame))
    except (TypeError, ValueError):
        return None


@app.callback(
    Output("frame-id", "value", allow_duplicate=True),
    Output("clicked-frame", "data"),
    Input("globe", "clickData"),
    State("selected-frame", "data"),
    prevent_initial_call=True,
)
def select_clicked_image(click_data: dict | None, selected_id: str | None):
    """Show the clicked photo's details in the side panel; it stays on the globe.

    The photo is the one under the cursor, identified like its hover label by
    the frame ID each mosaic vertex carries (``customdata``), so overlapping
    photos resolve to the one on top. Clicks on the selected photo, which has
    no ``customdata``, or off the photos change nothing. Also records the
    photo as clicked, so the view does not move to it.
    """
    points = (click_data or {}).get("points") or [{}]
    frame_id = _clicked_frame_id(points[0])
    if frame_id is None or frame_id == selected_id:
        return no_update, no_update
    return frame_id, frame_id


@app.callback(
    Output("frame-id", "value", allow_duplicate=True),
    Input("random-frame", "n_clicks"),
    State("frame-select", "options"),
    prevent_initial_call=True,
)
def select_random_frame(_clicks: int, frame_ids: list[str] | None):
    """Load a random frame of the selected mission."""
    if not frame_ids:
        return no_update
    return random.choice(frame_ids)


@app.callback(
    Output("frame-id", "value"),
    Input("frame-select", "value"),
    prevent_initial_call=True,
)
def select_frame(frame_id: str | None):
    """Load the frame chosen in the selector."""
    return frame_id or no_update


def _cached_metadata(frame_id: str) -> FrameMetadata | None:
    """LPI metadata from the disk cache; ``None`` if missing or unreadable."""
    try:
        return LOADER.store.metadata(frame_id)
    except (OSError, ValueError):
        return None


def _mission_tiles(mission: int | None) -> list[GlobeImage]:
    return list(LOADER.progress(mission).tiles.values()) if mission else []


@app.callback(
    Output("download-csv", "data"),
    Input("export-csv", "n_clicks"),
    State("mission-select", "value"),
    prevent_initial_call=True,
)
def export_csv(_clicks: int, mission: int | None):
    """Download the metadata of the mission's loaded frames as CSV."""
    tiles = _mission_tiles(mission)
    if not tiles:
        return no_update
    return {
        "content": mission_csv(tiles, _cached_metadata),
        "filename": f"lunar-orbiter-{mission}-frames.csv",
        "type": "text/csv",
    }


@app.callback(
    Output("download-geojson", "data"),
    Input("export-geojson", "n_clicks"),
    State("mission-select", "value"),
    prevent_initial_call=True,
)
def export_geojson(_clicks: int, mission: int | None):
    """Download the footprints of the mission's loaded frames as GeoJSON."""
    tiles = _mission_tiles(mission)
    if not tiles:
        return no_update
    return {
        "content": footprints_geojson(tiles),
        "filename": f"lunar-orbiter-{mission}-footprints.geojson",
        "type": "application/geo+json",
    }


def main() -> None:
    """Run the viewer on the host and port from ``config.json``."""
    print(f"Lunar Orbiter viewer: {CONFIG.url}")
    app.run(host=CONFIG.host, port=CONFIG.port, debug=False)


if __name__ == "__main__":
    main()
