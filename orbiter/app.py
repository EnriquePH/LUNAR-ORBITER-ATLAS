"""Local Dash app for viewing Lunar Orbiter frames on a 3D lunar globe."""

from __future__ import annotations

import base64
from io import BytesIO
from urllib.parse import parse_qs

import numpy as np
import requests
from dash import Dash, Input, Output, State, dcc, html, no_update
from PIL import Image

from orbiter.catalog import MissionLoader, TileStore, default_cache_dir
from orbiter.config import load_config
from orbiter.globe import (
    GlobeImage,
    format_coordinates,
    image_at,
    make_globe,
    visible_images,
)
from orbiter.i18n import LANGUAGES, normalize_language, t
from orbiter.lpi import LpiError, OrbiterFrame, fetch_frame, fetch_mission_frames
from orbiter.reference import moon_tab, program_tab
from orbiter.urls import MISSIONS_NUM, frame_url

DEFAULT_FRAME_ID = "1041"
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


def metadata_rows(frame: OrbiterFrame, lang: str = "es") -> list[html.Div]:
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
                    dcc.Graph(
                        id="globe",
                        figure=make_globe(),
                        className="globe-render",
                        config={"displayModeBar": False, "responsive": True},
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
                                [
                                    html.Div(
                                        t(lang, "mosaic_preparing"),
                                        id="mosaic-status",
                                        className="status-line",
                                    ),
                                    html.Button(
                                        t(lang, "show_hidden", count=0),
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
                                        t(lang, "load_button"),
                                        id="load-frame",
                                        n_clicks=0,
                                        className="load-button",
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
            dcc.Store(id="hidden-frames", data=[]),
            dcc.Store(id="mosaic-count", data=0),
            html.Header(
                [
                    html.Div(
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
                        className="wordmark",
                    ),
                    html.Div(
                        [
                            html.Div(t(lang, "top_meta"), className="top-meta"),
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
    """Redraw the globe: the mission's loaded tiles, minus hidden ones."""
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
    State("lang", "data"),
    prevent_initial_call="initial_duplicate",
)
def list_mission_frames(mission: int, lang: str = "es"):
    """Fill the frame selector and start downloading the mission's mosaic."""
    try:
        frame_ids = fetch_mission_frames(mission)
    except requests.RequestException as error:
        status = t(lang, "status_connection_error", error=error)
        return [], None, True, status, True, 0, []
    except ValueError as error:
        status = t(lang, "status_load_error", error=describe_error(lang, error))
        return [], None, True, status, True, 0, []
    LOADER.start(mission)
    status = t(lang, "status_mission_frames", mission=mission, count=len(frame_ids))
    return frame_ids, None, False, status, False, 0, []


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
    State("lang", "data"),
)
def describe_hidden(hidden: list[str] | None, lang: str = "es"):
    """Label the «show hidden» button with the count; disable it at zero."""
    count = len(hidden or ())
    return t(lang, "show_hidden", count=count), count == 0


@app.callback(
    Output("hidden-frames", "data", allow_duplicate=True),
    Input("show-hidden", "n_clicks"),
    prevent_initial_call=True,
)
def show_hidden(_clicks: int):
    """Make every hidden photo visible again."""
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


def main() -> None:
    """Run the viewer on the host and port from ``config.json``."""
    print(f"Lunar Orbiter viewer: {CONFIG.url}")
    app.run(host=CONFIG.host, port=CONFIG.port, debug=False)


if __name__ == "__main__":
    main()
