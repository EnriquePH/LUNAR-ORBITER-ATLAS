"""Plotly figure for the lunar globe: base sphere, frame tiles and selection.

Frames are placed schematically: each one is a north-up patch centred on its
principal point, sized from the spacecraft altitude when the LPI lists it. This
is a visual aid, not a photogrammetric footprint or a map projection: camera
tilt, frame orientation and terrain are ignored, so oblique shots look wrong.

Coordinates are selenographic degrees (north and east positive, longitudes in
-180..180 or any equivalent value). The globe is a unit sphere in Plotly scene
coordinates; ``x`` points to 0° E, ``y`` to 90° E and ``z`` to the north pole.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Iterable
from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go
from PIL import Image

ACCENT = "#ff7547"
BASE_SURFACE_VALUE = 112.0
MOON_RADIUS_KM = 1737.4
# Ground width covered per km of altitude by the medium-resolution camera
# (about 31.6 x 37.4 km from 46 km); a rough, nadir-only approximation.
FOOTPRINT_PER_ALTITUDE = 0.75
FALLBACK_PATCH_DEGREES = 6.0
MIN_PATCH_DEGREES = 0.5
MAX_PATCH_DEGREES = 30.0
# Tiles float just above the base sphere; the small per-tile step keeps
# overlapping tiles from flickering against each other.
TILE_RADIUS = 1.003
TILE_RADIUS_STEP = 0.0004
SELECTED_RADIUS = 1.006
CAMERA_DISTANCE = 1.6
REFERENCE_COLOR = "#8fb3c9"
# Pole labels sit just outside the sphere; the axis range must include them.
POLE_LABEL_HEIGHT = 1.18
AXIS_LIMIT = 1.25
# Plotly colours meshes per vertex, so every texture pixel is a vertex. Tiles get
# pixels in proportion to their size on the globe, within these bounds, and the
# whole mosaic is scaled down to stay under the vertex budget.
TILE_PIXELS_PER_DEGREE = 3.0
MIN_TILE_PIXELS = 10
MAX_TILE_PIXELS = 48
MESH_VERTEX_BUDGET = 90_000
GRAY_SCALE = [[0.0, "#000000"], [1.0, "#ffffff"]]
NO_CONTOURS = {axis: {"highlight": False} for axis in ("x", "y", "z")}


@dataclass(frozen=True, eq=False)
class GlobeImage:
    """Anything drawable on the globe: an ID, a position and a texture.

    Attributes:
        frame_id: Numeric LPI frame ID as text; also used as the hover label.
        latitude: Principal point latitude in degrees (-90..90).
        longitude: Principal point longitude in degrees.
        altitude_km: Spacecraft altitude in km, or ``None`` if unknown; it
            sets the patch size (see :func:`patch_width_degrees`).
        texture: 2-D ``uint8`` grayscale array (rows north to south, columns
            west to east), 0 black to 255 white. Its aspect sets the patch's.
    """

    frame_id: str
    latitude: float
    longitude: float
    altitude_km: float | None
    texture: np.ndarray


def format_coordinates(latitude: float, longitude: float) -> str:
    """Format signed degrees with hemisphere letters (N/S, E/W)."""
    latitude_hemisphere = "N" if latitude >= 0 else "S"
    longitude_hemisphere = "E" if longitude >= 0 else "W"
    return (
        f"{abs(latitude):.2f}° {latitude_hemisphere}  /  "
        f"{abs(longitude):.2f}° {longitude_hemisphere}"
    )


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


def to_latitude_longitude(x: float, y: float, z: float) -> tuple[float, float]:
    """Convert a scene point to (latitude, longitude) in degrees.

    The point may lie at any non-zero distance from the centre (tiles float
    slightly above the unit sphere). Longitude is returned in -180..180.
    """
    radius = math.sqrt(x * x + y * y + z * z)
    return math.degrees(math.asin(z / radius)), math.degrees(math.atan2(y, x))


def patch_width_degrees(altitude_km: float | None) -> float:
    """Approximate east-west ground width of a frame, in degrees of lunar arc.

    Uses ``FOOTPRINT_PER_ALTITUDE`` km of ground per km of altitude, derived
    from the medium-resolution camera looking straight down.

    Args:
        altitude_km: Spacecraft altitude in km, or ``None`` if unknown.

    Returns:
        ``FALLBACK_PATCH_DEGREES`` when the altitude is unknown; otherwise the
        estimate clamped to ``MIN_PATCH_DEGREES``..``MAX_PATCH_DEGREES``.
    """
    if altitude_km is None:
        return FALLBACK_PATCH_DEGREES
    width_km = FOOTPRINT_PER_ALTITUDE * altitude_km
    degrees = math.degrees(width_km / MOON_RADIUS_KM)
    return min(max(degrees, MIN_PATCH_DEGREES), MAX_PATCH_DEGREES)


def _patch_extent(image: GlobeImage) -> tuple[float, float]:
    """Return (latitude span, longitude span) in degrees."""
    height, width = image.texture.shape
    width_degrees = patch_width_degrees(image.altitude_km)
    latitude_span = width_degrees * height / width
    # Widen longitudes with latitude so the patch keeps its aspect on the sphere.
    longitude_span = width_degrees / max(math.cos(math.radians(image.latitude)), 0.2)
    return latitude_span, longitude_span


def patch_contains(image: GlobeImage, latitude: float, longitude: float) -> bool:
    """Tell whether a point in degrees falls inside an image's patch.

    Longitudes are compared modulo 360°, so patches that cross the 180°
    meridian work and ``-170`` and ``190`` are the same longitude.
    """
    latitude_span, longitude_span = _patch_extent(image)
    delta_longitude = (longitude - image.longitude + 180) % 360 - 180
    return (
        abs(latitude - image.latitude) <= latitude_span / 2
        and abs(delta_longitude) <= longitude_span / 2
    )


def image_at(
    images: Iterable[GlobeImage], x: float, y: float, z: float
) -> GlobeImage | None:
    """Return the image under a clicked point; overlaps go to the nearest centre."""
    latitude, longitude = to_latitude_longitude(x, y, z)
    hits = [image for image in images if patch_contains(image, latitude, longitude)]
    if not hits:
        return None
    return min(
        hits,
        key=lambda image: (
            (image.latitude - latitude) ** 2
            + ((image.longitude - longitude + 180) % 360 - 180) ** 2
        ),
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


def _patch_grid(
    image: GlobeImage, radius: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cartesian grid with one vertex per texture pixel."""
    height, width = image.texture.shape
    latitude_span, longitude_span = _patch_extent(image)
    # Image rows run north to south; columns run west to east.
    latitudes = np.clip(
        np.linspace(
            image.latitude + latitude_span / 2,
            image.latitude - latitude_span / 2,
            height,
        ),
        -90,
        90,
    )
    longitudes = np.linspace(
        image.longitude - longitude_span / 2,
        image.longitude + longitude_span / 2,
        width,
    )
    latitude_grid, longitude_grid = np.meshgrid(latitudes, longitudes, indexing="ij")
    return _to_cartesian(latitude_grid, longitude_grid, radius)


def _image_surface(image: GlobeImage, radius: float) -> go.Surface:
    x_coordinates, y_coordinates, z_coordinates = _patch_grid(image, radius)
    return go.Surface(
        x=x_coordinates.astype(np.float32),
        y=y_coordinates.astype(np.float32),
        z=z_coordinates.astype(np.float32),
        surfacecolor=image.texture,
        colorscale=GRAY_SCALE,
        cmin=0,
        cmax=255,
        showscale=False,
        name=image.frame_id,
        hovertemplate="%{fullData.name}<extra></extra>",
        contours=NO_CONTOURS,
        lighting={"ambient": 0.8, "diffuse": 0.4, "specular": 0.0},
    )


def _grid_triangles(height: int, width: int, offset: int) -> np.ndarray:
    """Two triangles per grid cell, as (n, 3) vertex indices."""
    rows, columns = np.meshgrid(
        np.arange(height - 1), np.arange(width - 1), indexing="ij"
    )
    top_left = (rows * width + columns).ravel() + offset
    top_right, bottom_left = top_left + 1, top_left + width
    bottom_right = bottom_left + 1
    return np.concatenate(
        [
            np.stack([top_left, bottom_left, top_right], axis=1),
            np.stack([top_right, bottom_left, bottom_right], axis=1),
        ]
    )


def _resized(texture: np.ndarray, long_side: int) -> np.ndarray:
    """Resize a texture so its longer side is ``long_side``, keeping its aspect."""
    height, width = texture.shape
    scale = long_side / max(height, width)
    size = (max(2, round(width * scale)), max(2, round(height * scale)))
    if size == (width, height):
        return texture
    image = Image.fromarray(texture).resize(size, Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.uint8)


def tile_textures(tiles: list[GlobeImage]) -> list[np.ndarray]:
    """Choose each tile's mesh resolution from its size on the globe.

    Big patches (high-altitude frames) get up to ``MAX_TILE_PIXELS`` on their
    longer side and tiny ones ``MIN_TILE_PIXELS``. If the mosaic would exceed
    ``MESH_VERTEX_BUDGET`` vertices, every tile shrinks by the same factor.
    Textures are never enlarged beyond what the tile provides.
    """
    wanted = [
        min(
            max(
                round(TILE_PIXELS_PER_DEGREE * patch_width_degrees(tile.altitude_km)),
                MIN_TILE_PIXELS,
            ),
            MAX_TILE_PIXELS,
            max(tile.texture.shape),
        )
        for tile in tiles
    ]
    # Vertices are about long_side² × aspect, so area scales with the square.
    area = sum(
        side * side * min(tile.texture.shape) / max(tile.texture.shape)
        for side, tile in zip(wanted, tiles, strict=True)
    )
    factor = min(1.0, math.sqrt(MESH_VERTEX_BUDGET / area)) if area else 1.0
    return [
        _resized(tile.texture, max(2, math.floor(side * factor)))
        for side, tile in zip(wanted, tiles, strict=True)
    ]


def _tiles_mesh(tiles: list[GlobeImage]) -> go.Mesh3d:
    """Merge every tile into one mesh: one WebGL draw call instead of hundreds.

    Frame IDs travel as per-vertex ``int16`` ``customdata`` and brightness as
    ``uint8`` intensity; Plotly sends both in binary, which keeps the payload
    small while still labelling each photo on hover.
    """
    coordinates, intensities, triangles, frame_ids = [], [], [], []
    offset = 0
    for index, (tile, texture) in enumerate(
        zip(tiles, tile_textures(tiles), strict=True)
    ):
        radius = TILE_RADIUS + TILE_RADIUS_STEP * (index % 7)
        resized = GlobeImage(
            tile.frame_id, tile.latitude, tile.longitude, tile.altitude_km, texture
        )
        grid = np.stack([axis.ravel() for axis in _patch_grid(resized, radius)], axis=1)
        height, width = texture.shape
        coordinates.append(grid)
        intensities.append(texture.ravel())
        triangles.append(_grid_triangles(height, width, offset))
        frame_ids.append(np.full(len(grid), int(tile.frame_id), dtype=np.int16))
        offset += len(grid)

    vertices = np.concatenate(coordinates).astype(np.float32)
    faces = np.concatenate(triangles).astype(np.int32)
    return go.Mesh3d(
        x=vertices[:, 0],
        y=vertices[:, 1],
        z=vertices[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        intensity=np.concatenate(intensities),
        intensitymode="vertex",
        colorscale=GRAY_SCALE,
        cmin=0,
        cmax=255,
        showscale=False,
        customdata=np.concatenate(frame_ids),
        hovertemplate="%{customdata}<extra></extra>",
        flatshading=False,
        lighting={"ambient": 0.8, "diffuse": 0.4, "specular": 0.0},
    )


def _marker(image: GlobeImage) -> go.Scatter3d:
    x_coordinate, y_coordinate, z_coordinate = _to_cartesian(
        image.latitude, image.longitude, 1.02
    )
    return go.Scatter3d(
        x=[x_coordinate],
        y=[y_coordinate],
        z=[z_coordinate],
        mode="markers+text",
        marker={"size": 4, "color": ACCENT},
        text=[image.frame_id],
        textposition="top center",
        textfont={"color": "#ff9c79", "family": "DM Mono, monospace", "size": 11},
        hovertext=[
            f"{image.frame_id} · {format_coordinates(image.latitude, image.longitude)}"
        ],
        hoverinfo="text",
    )


def _reference_marks() -> list[go.Scatter3d]:
    """Dotted equator plus labelled north and south poles.

    ``hoverinfo="skip"`` keeps them from producing hover or click events, so a
    click near the equator still reaches the photo underneath.
    """
    longitudes = np.linspace(-180, 180, 181)
    x_coordinates, y_coordinates, z_coordinates = _to_cartesian(
        np.zeros_like(longitudes), longitudes, 1.008
    )
    equator = go.Scatter3d(
        x=x_coordinates,
        y=y_coordinates,
        z=z_coordinates,
        name="equator",
        mode="lines",
        line={"color": REFERENCE_COLOR, "width": 2, "dash": "dot"},
        hoverinfo="skip",
    )
    poles = go.Scatter3d(
        x=[0, 0, 0, 0],
        y=[0, 0, 0, 0],
        z=[1.01, -1.01, POLE_LABEL_HEIGHT, -POLE_LABEL_HEIGHT],
        name="poles",
        mode="markers+text",
        marker={"size": [5, 5, 0, 0], "color": REFERENCE_COLOR},
        text=["", "", "N", "S"],
        textfont={"color": REFERENCE_COLOR, "family": "DM Mono, monospace", "size": 13},
        hoverinfo="skip",
    )
    return [equator, poles]


def _camera_eye(latitude: float, longitude: float) -> dict[str, float]:
    x_coordinate, y_coordinate, z_coordinate = _to_cartesian(
        latitude, longitude, CAMERA_DISTANCE
    )
    return {
        "x": float(x_coordinate),
        "y": float(y_coordinate),
        "z": float(z_coordinate),
    }


def visible_images(
    selected: GlobeImage | None,
    tiles: Iterable[GlobeImage],
    hidden: Collection[str],
) -> list[GlobeImage]:
    """Images drawn as textures; the selection replaces its own tile."""
    selected_id = selected.frame_id if selected else None
    images = [
        tile
        for tile in tiles
        if tile.frame_id not in hidden and tile.frame_id != selected_id
    ]
    if selected is not None and selected.frame_id not in hidden:
        images.append(selected)
    return images


def make_globe(
    selected: GlobeImage | None = None,
    tiles: Iterable[GlobeImage] = (),
    hidden: Collection[str] = (),
) -> go.Figure:
    """Build the globe with every visible tile and the selected frame on top.

    The camera centres on the selection; ``uirevision`` keeps the user's own
    rotation while tiles are added or hidden for the same selection.
    """
    tiles = sorted(tiles, key=lambda tile: tile.frame_id)
    images = visible_images(selected, tiles, hidden)
    mosaic = [image for image in images if image is not selected]
    traces: list[go.Surface | go.Mesh3d | go.Scatter3d] = [_base_sphere()]
    if mosaic:
        traces.append(_tiles_mesh(mosaic))
    if selected is not None and selected in images:
        traces.append(_image_surface(selected, SELECTED_RADIUS))
    traces += _reference_marks()
    if selected is not None:
        traces.append(_marker(selected))
        eye = _camera_eye(selected.latitude, selected.longitude)
    elif tiles:
        eye = _camera_eye(tiles[0].latitude, tiles[0].longitude)
    else:
        eye = _camera_eye(22, 35)

    hidden_axis = {"visible": False, "range": [-AXIS_LIMIT, AXIS_LIMIT]}
    figure = go.Figure(traces)
    figure.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font={"family": "DM Mono, monospace"},
        hoverlabel={
            "bgcolor": "#181a1b",
            "bordercolor": ACCENT,
            "font": {"family": "DM Mono, monospace", "color": "#e6e3dd", "size": 11},
        },
        uirevision=selected.frame_id if selected else "globe",
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
