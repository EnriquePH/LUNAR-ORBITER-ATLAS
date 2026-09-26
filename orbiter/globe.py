"""Plotly figure for the lunar globe: base sphere, frame tiles and selection.

Frames are placed schematically: each one is a north-up patch centred on its
principal point, sized from the spacecraft altitude when the LPI lists it.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Iterable
from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go

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
GRAY_SCALE = [[0.0, "#000000"], [1.0, "#ffffff"]]
NO_CONTOURS = {axis: {"highlight": False} for axis in ("x", "y", "z")}


@dataclass(frozen=True, eq=False)
class GlobeImage:
    """Anything drawable on the globe: an ID, a position and a texture."""

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
    radius = math.sqrt(x * x + y * y + z * z)
    return math.degrees(math.asin(z / radius)), math.degrees(math.atan2(y, x))


def patch_width_degrees(altitude_km: float | None) -> float:
    """Approximate ground width of a frame, as degrees of lunar arc."""
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


def _image_surface(image: GlobeImage, radius: float) -> go.Surface:
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
    x_coordinates, y_coordinates, z_coordinates = _to_cartesian(
        latitude_grid, longitude_grid, radius
    )
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
    traces: list[go.Surface | go.Scatter3d] = [_base_sphere()]
    for index, image in enumerate(visible_images(selected, tiles, hidden)):
        is_selected = selected is not None and image.frame_id == selected.frame_id
        radius = (
            SELECTED_RADIUS
            if is_selected
            else TILE_RADIUS + TILE_RADIUS_STEP * (index % 7)
        )
        traces.append(_image_surface(image, radius))
    if selected is not None:
        traces.append(_marker(selected))
        eye = _camera_eye(selected.latitude, selected.longitude)
    elif tiles:
        eye = _camera_eye(tiles[0].latitude, tiles[0].longitude)
    else:
        eye = _camera_eye(22, 35)

    hidden_axis = {"visible": False, "range": [-1.1, 1.1]}
    figure = go.Figure(traces)
    figure.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
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
