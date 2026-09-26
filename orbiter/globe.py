"""Plotly figure for the lunar globe: base sphere, frame tiles and selection.

When the LPI lists the spacecraft position, a frame is **projected**: every
pixel becomes a ray from the spacecraft through the camera aimed at the
principal point, and lands where that ray meets the Moon. Oblique and
high-altitude shots therefore cover the part of the sphere they actually
photographed; pixels that see sky or the Earth fall off the Moon and are
dropped. The image's roll is not published and is inferred (see
:func:`frame_camera`). Terrain is ignored.

The LPI thumbnail shows the medium-resolution frame (80 mm lens) when the
gallery has one, and otherwise the middle third of the high-resolution frame
(610 mm lens), which is centred on the same principal point.

Frames without a spacecraft position fall back to a north-up patch centred on
the principal point, sized from the altitude.

Coordinates are selenographic degrees (north and east positive, longitudes in
-180..180 or any equivalent value). The globe is a unit sphere in Plotly scene
coordinates; ``x`` points to 0° E, ``y`` to 90° E and ``z`` to the north pole.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Iterable
from dataclasses import dataclass, replace

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
# (focal length, (short side, long side)) in mm. Medium resolution: 31.6 x 37.4
# km from 46 km. High resolution: the 55 x 218 mm frame is split into three
# sub-frames; thumbnails show the middle one.
CAMERAS = {
    "medium": (80.0, (55.0, 65.0)),
    "high": (610.0, (55.0, 218.0 / 3)),
}
# Above this altitude a frame covers a large, strongly curved area; it is
# outlined on the globe and flagged in the side panel.
HIGH_ALTITUDE_KM = 1000.0
OUTLINE_SAMPLES = 24
# Footprints (side panel and exports): samples along the central row and
# column, directions traced from the principal point for the outline, and
# bisection steps to find the limb on each (to 2^-30 of the frame).
FOOTPRINT_SAMPLES = 129
OUTLINE_RAYS = 96
LIMB_BISECTIONS = 30
# The LPI's emission angle must agree with the one implied by the spacecraft
# position; otherwise the metadata is inconsistent and the frame is not
# projected. Over 890 frames the median gap is 0.06° and 95% are under 0.35°.
EMISSION_TOLERANCE_DEGREES = 5.0
# Oblique frames are shown level, horizon up; near-vertical ones north-up.
LEVEL_CAMERA_MIN_EMISSION = 20.0
# High-altitude frames may be rolled so that their off-Moon pixels land on the
# texture's black sky: that area must be dark, clearly darker than the Moon,
# cover a real share of the frame, and beat the next roll by a clear margin.
SKY_MAX_BRIGHTNESS = 45.0
SKY_MATCH_MARGIN = 30.0
SKY_MIN_SHARE = 0.03
SKY_TIE_MARGIN = 10.0
CAMERA_CACHE_SIZE = 4096
# Tiles float just above the base sphere; the small per-tile step keeps
# overlapping tiles from flickering against each other.
TILE_RADIUS = 1.003
TILE_RADIUS_STEP = 0.0004
SELECTED_RADIUS = 1.006
CAMERA_DISTANCE = 1.6
REFERENCE_COLOR = "#8fb3c9"
# Frame IDs float just above the tiles, at each photo's principal point.
LABEL_RADIUS = 1.012
LABEL_COLOR = "#ffd9c9"
SELECTED_LABEL_COLOR = ACCENT
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
        altitude_km: Spacecraft altitude in km, or ``None`` if unknown.
        texture: 2-D ``uint8`` grayscale array (rows top to bottom), 0 black
            to 255 white. Its aspect sets the frame's.
        spacecraft_latitude: Spacecraft sub-point latitude in degrees, or
            ``None``. With the longitude and altitude it enables projection.
        spacecraft_longitude: Spacecraft sub-point longitude in degrees.
        emission_angle: LPI emission angle in degrees, used to reject
            inconsistent spacecraft positions; ``None`` skips the check.
        camera: ``"medium"`` (80 mm) or ``"high"`` (610 mm, middle sub-frame):
            which camera the texture comes from.
    """

    frame_id: str
    latitude: float
    longitude: float
    altitude_km: float | None
    texture: np.ndarray
    spacecraft_latitude: float | None = None
    spacecraft_longitude: float | None = None
    emission_angle: float | None = None
    camera: str = "medium"

    @property
    def is_high_altitude(self) -> bool:
        """Whether the frame was taken above ``HIGH_ALTITUDE_KM``."""
        return self.altitude_km is not None and self.altitude_km > HIGH_ALTITUDE_KM


@dataclass(frozen=True)
class FrameCamera:
    """Pinhole camera of one frame, in scene units (Moon radius = 1).

    Attributes:
        position: Spacecraft position.
        forward: Unit vector towards the principal point.
        right: Unit vector along the image's columns (east for north-up).
        up: Unit vector along the image's rows, towards the top of the image.
        half_width: Half the frame width divided by the focal length.
        half_height: Half the frame height divided by the focal length.
    """

    position: np.ndarray
    forward: np.ndarray
    right: np.ndarray
    up: np.ndarray
    half_width: float
    half_height: float

    def rays(self, horizontal: np.ndarray, vertical: np.ndarray) -> np.ndarray:
        """Unit ray directions for image-plane offsets in focal units."""
        directions = (
            self.forward
            + horizontal[..., None] * self.right
            + vertical[..., None] * self.up
        )
        return directions / np.linalg.norm(directions, axis=-1, keepdims=True)

    def hit_sphere(self, directions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Intersect rays with the unit sphere.

        Returns:
            The nearest hit points (NaN where a ray misses) and a mask of hits.
        """
        b = directions @ self.position
        c = float(self.position @ self.position) - 1.0
        discriminant = b * b - c
        hit = discriminant >= 0
        distance = -b - np.sqrt(np.where(hit, discriminant, 0.0))
        hit &= distance > 0
        points = self.position + distance[..., None] * directions
        points[~hit] = np.nan
        return points, hit

    def sees(self, point: np.ndarray) -> bool:
        """Whether a point on the unit sphere is visible inside the frame."""
        view = point - self.position
        if float(point @ -view) <= 0:  # on the far side of the Moon
            return False
        depth = float(view @ self.forward)
        if depth <= 0:
            return False
        horizontal = float(view @ self.right) / depth
        vertical = float(view @ self.up) / depth
        return abs(horizontal) <= self.half_width and abs(vertical) <= self.half_height


def camera_of(preview_url: str) -> str:
    """Tell which camera a frame's LPI preview (and thumbnail) comes from.

    Args:
        preview_url: URL chosen by :func:`orbiter.lpi.parse_frame_page`, which
            prefers the medium-resolution ``_med`` image when there is one.

    Returns:
        ``"medium"`` for ``..._med.jpg``, otherwise ``"high"``.
    """
    return "medium" if preview_url.lower().endswith("_med.jpg") else "high"


def frame_camera(image: GlobeImage) -> FrameCamera | None:
    """Build the camera of a frame, or ``None`` if it cannot be projected.

    Returns ``None`` without a spacecraft position, when the principal point
    would not be visible from the spacecraft, or when the implied emission
    angle disagrees with the LPI's by more than ``EMISSION_TOLERANCE_DEGREES``
    (a few frames have inconsistent metadata).

    The image's roll is not published, so it is inferred:

    - near-vertical frames (emission under ``LEVEL_CAMERA_MIN_EMISSION``) are
      north-up;
    - oblique frames are level, with the horizon at the top of the image, as
      the LPI shows them;
    - high-altitude frames that see past the limb take the quarter-turn whose
      off-Moon pixels fall on the texture's black sky, when one clearly does.

    Cameras are cached per frame geometry, so the roll search runs once.
    """
    key = (
        image.frame_id,
        image.latitude,
        image.longitude,
        image.altitude_km,
        image.spacecraft_latitude,
        image.spacecraft_longitude,
        image.emission_angle,
        image.camera,
        image.texture.shape[0] >= image.texture.shape[1],
    )
    if key not in _CAMERA_CACHE:
        if len(_CAMERA_CACHE) >= CAMERA_CACHE_SIZE:
            _CAMERA_CACHE.clear()
        _CAMERA_CACHE[key] = _build_camera(image)
    return _CAMERA_CACHE[key]


_CAMERA_CACHE: dict[tuple, FrameCamera | None] = {}


def _view(image: GlobeImage) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Spacecraft position, principal point, view direction and emission (°)."""
    position = np.array(
        selenographic_to_cartesian(
            image.spacecraft_latitude,
            image.spacecraft_longitude,
            1.0 + image.altitude_km / MOON_RADIUS_KM,
        )
    )
    target = np.array(selenographic_to_cartesian(image.latitude, image.longitude))
    forward = target - position
    forward /= np.linalg.norm(forward)
    emission = math.degrees(math.acos(float(np.clip(-forward @ target, -1.0, 1.0))))
    return position, target, forward, emission


def _has_position(image: GlobeImage) -> bool:
    return (
        image.altitude_km is not None
        and image.spacecraft_latitude is not None
        and image.spacecraft_longitude is not None
    )


def implied_emission_angle(image: GlobeImage) -> float | None:
    """Emission angle implied by the spacecraft position, in degrees.

    It is the angle at the principal point between the local vertical and the
    direction to the spacecraft; :func:`frame_camera` compares it with the
    LPI's own value.

    Returns:
        The angle (0..180), or ``None`` without a spacecraft position.
    """
    return _view(image)[3] if _has_position(image) else None


def _build_camera(image: GlobeImage) -> FrameCamera | None:
    if not _has_position(image):
        return None
    position, target, forward, emission = _view(image)
    if emission >= 90.0:
        return None
    if (
        image.emission_angle is not None
        and abs(emission - image.emission_angle) > EMISSION_TOLERANCE_DEGREES
    ):
        return None

    if emission >= LEVEL_CAMERA_MIN_EMISSION:
        reference = target  # local vertical: a level camera, horizon at the top
    else:
        latitude, longitude = np.radians(image.latitude), np.radians(image.longitude)
        reference = np.array(
            [
                -np.sin(latitude) * np.cos(longitude),
                -np.sin(latitude) * np.sin(longitude),
                np.cos(latitude),
            ]
        )
    up = reference - (reference @ forward) * forward
    if np.linalg.norm(up) < 1e-9:  # looking straight along the reference
        up = np.cross(forward, [0.0, 0.0, 1.0] if abs(forward[2]) < 0.9 else [1, 0, 0])
    up /= np.linalg.norm(up)
    right = np.cross(forward, up)

    height, width = image.texture.shape
    focal, (short, long) = CAMERAS[image.camera]
    frame_width, frame_height = (short, long) if height >= width else (long, short)
    base = FrameCamera(
        position=position,
        forward=forward,
        right=right,
        up=up,
        half_width=frame_width / 2 / focal,
        half_height=frame_height / 2 / focal,
    )
    return _match_sky(base, image.texture) if image.is_high_altitude else base


def _rolled(camera: FrameCamera, quarter_turns: int) -> FrameCamera:
    """Rotate the camera about its view axis by 90° steps."""
    angle = quarter_turns * math.pi / 2
    cosine, sine = round(math.cos(angle)), round(math.sin(angle))
    return replace(
        camera,
        right=cosine * camera.right + sine * camera.up,
        up=-sine * camera.right + cosine * camera.up,
    )


def _sky_contrast(camera: FrameCamera, texture: np.ndarray) -> float | None:
    """How much darker the predicted sky is than the Moon, if it looks like sky.

    Returns ``None`` unless both areas cover ``SKY_MIN_SHARE`` of the frame
    and the predicted sky is darker than ``SKY_MAX_BRIGHTNESS``.
    """
    height, width = texture.shape
    horizontal, vertical = np.meshgrid(
        np.linspace(-camera.half_width, camera.half_width, width),
        np.linspace(camera.half_height, -camera.half_height, height),
    )
    _, on_moon = camera.hit_sphere(camera.rays(horizontal, vertical))
    sky_share = 1.0 - on_moon.mean()
    if not SKY_MIN_SHARE <= sky_share <= 1.0 - SKY_MIN_SHARE:
        return None
    sky = float(texture[~on_moon].mean())
    if sky > SKY_MAX_BRIGHTNESS:
        return None
    return float(texture[on_moon].mean()) - sky


def _match_sky(camera: FrameCamera, texture: np.ndarray) -> FrameCamera:
    """Pick the quarter-turn whose off-Moon pixels are the texture's black sky.

    Keeps ``camera`` unless one roll is clearly the best match.
    """
    candidates = [_rolled(camera, turns) for turns in range(4)]
    contrasts = [_sky_contrast(candidate, texture) for candidate in candidates]
    ranked = sorted(
        (
            (contrast, turns)
            for turns, contrast in enumerate(contrasts)
            if contrast is not None and contrast >= SKY_MATCH_MARGIN
        ),
        reverse=True,
    )
    if not ranked or ranked[0][1] == 0:
        return camera
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < SKY_TIE_MARGIN:
        return camera
    return candidates[ranked[0][1]]


@dataclass(frozen=True)
class FrameGeometry:
    """Ground size of a frame and how it was placed on the globe.

    Attributes:
        width_km: Ground length across the image through its centre, in km.
        height_km: Ground length along the image through its centre, in km.
            For projected frames only the part that lands on the Moon counts.
        projected: ``True`` if the frame is projected from the spacecraft,
            ``False`` if it falls back to the approximate north-up patch.
        implied_emission: Emission angle implied by the spacecraft position,
            in degrees, or ``None`` without one.
    """

    width_km: float
    height_km: float
    projected: bool
    implied_emission: float | None


def _border_distances(camera: FrameCamera, angles: np.ndarray) -> np.ndarray:
    """How far the footprint reaches from the principal point, per direction.

    The part of the image plane that sees the Moon is convex and contains the
    principal point, so along each direction (radians, 0 towards ``right``,
    π/2 towards ``up``) it ends at the frame's edge or, before that, at the
    limb, found by ``LIMB_BISECTIONS`` bisection steps.

    Returns:
        Distances in focal units, one per angle.
    """
    cosines, sines = np.cos(angles), np.sin(angles)
    with np.errstate(divide="ignore"):
        edge = np.minimum(
            camera.half_width / np.abs(cosines), camera.half_height / np.abs(sines)
        )

    def hits(distance: np.ndarray) -> np.ndarray:
        return camera.hit_sphere(camera.rays(distance * cosines, distance * sines))[1]

    inside, outside = np.zeros_like(edge), edge.copy()
    past_limb = ~hits(edge)
    inside[~past_limb] = edge[~past_limb]
    for _ in range(LIMB_BISECTIONS):
        middle = (inside + outside) / 2
        hit = hits(middle)
        inside = np.where(past_limb & hit, middle, inside)
        outside = np.where(past_limb & ~hit, middle, outside)
    return inside


def _ground_length_km(camera: FrameCamera, horizontal, vertical) -> float:
    """Length on the Moon of an image-plane polyline whose rays all hit it."""
    points, _ = camera.hit_sphere(camera.rays(horizontal, vertical))
    cosines = np.einsum("ij,ij->i", points[:-1], points[1:])
    return float(np.arccos(np.clip(cosines, -1.0, 1.0)).sum()) * MOON_RADIUS_KM


def frame_geometry(image: GlobeImage) -> FrameGeometry:
    """Measure a frame's footprint as drawn on the globe.

    Projected frames are measured along the image's central row and column,
    up to the frame's edges or the limb.
    Fallback patches use :func:`patch_width_degrees`, a rough nadir estimate,
    with the texture's aspect.
    """
    camera = frame_camera(image)
    if camera is None:
        width_km = (
            math.radians(patch_width_degrees(image.altitude_km, image.camera))
            * MOON_RADIUS_KM
        )
        height, width = image.texture.shape
        return FrameGeometry(
            width_km=width_km,
            height_km=width_km * height / width,
            projected=False,
            implied_emission=implied_emission_angle(image),
        )
    right, up, left, down = _border_distances(
        camera, np.array([0.0, np.pi / 2, np.pi, -np.pi / 2])
    )
    zeros = np.zeros(FOOTPRINT_SAMPLES)
    across = np.linspace(-left, right, FOOTPRINT_SAMPLES)
    along = np.linspace(-down, up, FOOTPRINT_SAMPLES)
    return FrameGeometry(
        width_km=_ground_length_km(camera, across, zeros),
        height_km=_ground_length_km(camera, zeros, along),
        projected=True,
        implied_emission=implied_emission_angle(image),
    )


def format_coordinates(latitude: float, longitude: float) -> str:
    """Format signed degrees with hemisphere letters (N/S, E/W)."""
    latitude_hemisphere = "N" if latitude >= 0 else "S"
    longitude_hemisphere = "E" if longitude >= 0 else "W"
    return (
        f"{abs(latitude):.2f}° {latitude_hemisphere}  /  "
        f"{abs(longitude):.2f}° {longitude_hemisphere}"
    )


def selenographic_to_cartesian(
    latitude_degrees: np.ndarray | float,
    longitude_degrees: np.ndarray | float,
    radius: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert selenographic degrees to scene coordinates.

    Args:
        latitude_degrees: Latitude in degrees, north positive; scalar or array.
        longitude_degrees: Longitude in degrees, east positive; any equivalent
            value (``-170`` and ``190`` give the same point).
        radius: Distance from the centre, in Moon radii (1 is the surface).

    Returns:
        ``(x, y, z)``: ``x`` towards 0° E, ``y`` towards 90° E, ``z`` towards
        the north pole; arrays shaped like the inputs. Inverse of
        :func:`cartesian_to_selenographic`.
    """
    latitudes = np.radians(latitude_degrees)
    longitudes = np.radians(longitude_degrees)
    return (
        radius * np.cos(latitudes) * np.cos(longitudes),
        radius * np.cos(latitudes) * np.sin(longitudes),
        radius * np.sin(latitudes),
    )


def cartesian_to_selenographic(x: float, y: float, z: float) -> tuple[float, float]:
    """Convert a scene point to (latitude, longitude) in degrees.

    The point may lie at any non-zero distance from the centre (tiles float
    slightly above the unit sphere). Longitude is returned in -180..180.
    Inverse of :func:`selenographic_to_cartesian`.

    Raises:
        ZeroDivisionError: For the centre point ``(0, 0, 0)``.
    """
    radius = math.sqrt(x * x + y * y + z * z)
    return math.degrees(math.asin(z / radius)), math.degrees(math.atan2(y, x))


def patch_width_degrees(altitude_km: float | None, camera: str = "medium") -> float:
    """Approximate east-west ground width of a frame, in degrees of lunar arc.

    Uses ``FOOTPRINT_PER_ALTITUDE`` km of ground per km of altitude, derived
    from the medium-resolution camera looking straight down, scaled by focal
    length for the high-resolution one.

    Args:
        altitude_km: Spacecraft altitude in km, or ``None`` if unknown.
        camera: ``"medium"`` or ``"high"``.

    Returns:
        ``FALLBACK_PATCH_DEGREES`` when the altitude is unknown; otherwise the
        estimate clamped to ``MIN_PATCH_DEGREES``..``MAX_PATCH_DEGREES``.
    """
    if altitude_km is None:
        return FALLBACK_PATCH_DEGREES
    focal_ratio = CAMERAS["medium"][0] / CAMERAS[camera][0]
    width_km = FOOTPRINT_PER_ALTITUDE * focal_ratio * altitude_km
    degrees = math.degrees(width_km / MOON_RADIUS_KM)
    return min(max(degrees, MIN_PATCH_DEGREES), MAX_PATCH_DEGREES)


def _patch_extent(image: GlobeImage) -> tuple[float, float]:
    """Return (latitude span, longitude span) in degrees."""
    height, width = image.texture.shape
    width_degrees = patch_width_degrees(image.altitude_km, image.camera)
    latitude_span = width_degrees * height / width
    # Widen longitudes with latitude so the patch keeps its aspect on the sphere.
    longitude_span = width_degrees / max(math.cos(math.radians(image.latitude)), 0.2)
    return latitude_span, longitude_span


def patch_contains(image: GlobeImage, latitude: float, longitude: float) -> bool:
    """Tell whether a point in degrees falls inside an image's footprint.

    Projected frames test whether the camera saw the point. Fallback patches
    compare longitudes modulo 360°, so patches that cross the 180° meridian
    work and ``-170`` and ``190`` are the same longitude.
    """
    camera = frame_camera(image)
    if camera is not None:
        return camera.sees(np.array(selenographic_to_cartesian(latitude, longitude)))
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
    latitude, longitude = cartesian_to_selenographic(x, y, z)
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
    x_coordinates, y_coordinates, z_coordinates = selenographic_to_cartesian(
        latitudes, longitudes
    )
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
    """Cartesian grid with one vertex per texture pixel.

    Projected frames put each vertex where its pixel's ray meets the Moon;
    pixels whose rays miss (sky, the Earth) are NaN.
    """
    height, width = image.texture.shape
    camera = frame_camera(image)
    if camera is not None:
        horizontal, vertical = np.meshgrid(
            np.linspace(-camera.half_width, camera.half_width, width),
            np.linspace(camera.half_height, -camera.half_height, height),
        )
        points, _ = camera.hit_sphere(camera.rays(horizontal, vertical))
        points *= radius
        return points[..., 0], points[..., 1], points[..., 2]

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
    return selenographic_to_cartesian(latitude_grid, longitude_grid, radius)


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
                round(
                    TILE_PIXELS_PER_DEGREE
                    * patch_width_degrees(tile.altitude_km, tile.camera)
                ),
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
        resized = replace(tile, texture=texture)
        grid = np.stack([axis.ravel() for axis in _patch_grid(resized, radius)], axis=1)
        height, width = texture.shape
        # Drop triangles that touch a pixel whose ray missed the Moon.
        on_moon = ~np.isnan(grid[:, 0])
        cells = _grid_triangles(height, width, 0)
        cells = cells[on_moon[cells].all(axis=1)]
        grid[~on_moon] = 0.0
        coordinates.append(grid)
        intensities.append(texture.ravel())
        triangles.append(cells + offset)
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


def _outline(image: GlobeImage, radius: float) -> np.ndarray:
    """Points along a frame's border on the sphere, ending with a NaN break."""
    samples = np.linspace(-1.0, 1.0, OUTLINE_SAMPLES)
    camera = frame_camera(image)
    if camera is not None:
        width, height = camera.half_width, camera.half_height
        horizontal = np.concatenate(
            [
                samples * width,
                np.full_like(samples, width),
                -samples * width,
                np.full_like(samples, -width),
            ]
        )
        vertical = np.concatenate(
            [
                np.full_like(samples, height),
                -samples * height,
                np.full_like(samples, -height),
                samples * height,
            ]
        )
        points, _ = camera.hit_sphere(camera.rays(horizontal, vertical))
        points *= radius
    else:
        latitude_span, longitude_span = _patch_extent(image)
        half_lat, half_lon = latitude_span / 2, longitude_span / 2
        latitudes = image.latitude + np.concatenate(
            [
                np.full_like(samples, half_lat),
                -samples * half_lat,
                np.full_like(samples, -half_lat),
                samples * half_lat,
            ]
        )
        longitudes = image.longitude + np.concatenate(
            [
                samples * half_lon,
                np.full_like(samples, half_lon),
                -samples * half_lon,
                np.full_like(samples, -half_lon),
            ]
        )
        points = np.stack(
            selenographic_to_cartesian(np.clip(latitudes, -90, 90), longitudes, radius),
            axis=1,
        )
    return np.vstack([points, np.full((1, 3), np.nan)])


def footprint_outline(image: GlobeImage) -> list[tuple[float, float]]:
    """Border of a frame's footprint on the Moon, as drawn on the globe.

    For projected frames the border is the part of the image plane whose rays
    hit the Moon: the frame's edges, cut by the limb where the camera saw past
    it (a whole-disc shot gives the limb alone). That region is convex and
    contains the principal point, so the border is traced along
    ``OUTLINE_RAYS`` directions from it, plus the four corners; on each, the
    limb is found by bisection.

    Returns:
        ``(latitude, longitude)`` pairs in degrees going once round the
        footprint, longitudes in -180..180.
    """
    camera = frame_camera(image)
    if camera is None:
        return [
            cartesian_to_selenographic(*point) for point in _outline(image, 1.0)[:-1]
        ]
    width, height = camera.half_width, camera.half_height
    corners = np.arctan2(
        [height, height, -height, -height], [width, -width, -width, width]
    )
    angles = np.sort(
        np.concatenate(
            [np.linspace(-np.pi, np.pi, OUTLINE_RAYS, endpoint=False), corners]
        )
    )
    distances = _border_distances(camera, angles)
    points, _ = camera.hit_sphere(
        camera.rays(distances * np.cos(angles), distances * np.sin(angles))
    )
    return [cartesian_to_selenographic(*point) for point in points]


def _high_altitude_outlines(images: list[GlobeImage]) -> go.Scatter3d | None:
    """Outline frames taken above ``HIGH_ALTITUDE_KM`` so they stand out.

    ``hoverinfo="skip"`` lets clicks on the outline reach the photo below.
    """
    high = [image for image in images if image.is_high_altitude]
    if not high:
        return None
    points = np.vstack([_outline(image, SELECTED_RADIUS + 0.002) for image in high])
    return go.Scatter3d(
        x=points[:, 0],
        y=points[:, 1],
        z=points[:, 2],
        name="high-altitude",
        mode="lines",
        # Thin and translucent: mission 4 has 131 overlapping high frames.
        line={"color": REFERENCE_COLOR, "width": 1},
        opacity=0.4,
        connectgaps=False,
        hoverinfo="skip",
    )


def _frame_labels(
    images: list[GlobeImage], selected_id: str | None = None
) -> go.Scatter3d | None:
    """Frame ID at the centre of each photo (its principal point).

    The selected photo's label takes the accent colour and sits above its
    marker, so the photo shown in the side panel stands out.
    ``hoverinfo="skip"`` lets clicks on a label reach the photo below.
    """
    if not images:
        return None
    x_coordinates, y_coordinates, z_coordinates = selenographic_to_cartesian(
        np.array([image.latitude for image in images]),
        np.array([image.longitude for image in images]),
        LABEL_RADIUS,
    )
    selected = [image.frame_id == selected_id for image in images]
    return go.Scatter3d(
        x=x_coordinates,
        y=y_coordinates,
        z=z_coordinates,
        name="labels",
        mode="text",
        text=[image.frame_id for image in images],
        textposition=[
            "top center" if is_selected else "middle center" for is_selected in selected
        ],
        textfont={
            "color": [
                SELECTED_LABEL_COLOR if is_selected else LABEL_COLOR
                for is_selected in selected
            ],
            "size": [11 if is_selected else 9 for is_selected in selected],
            "family": "DM Mono, monospace",
        },
        hoverinfo="skip",
    )


def _marker(image: GlobeImage) -> go.Scatter3d:
    """Accent dot on the selection; its label is in :func:`_frame_labels`."""
    x_coordinate, y_coordinate, z_coordinate = selenographic_to_cartesian(
        image.latitude, image.longitude, 1.02
    )
    return go.Scatter3d(
        x=[x_coordinate],
        y=[y_coordinate],
        z=[z_coordinate],
        mode="markers",
        marker={"size": 4, "color": ACCENT},
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
    x_coordinates, y_coordinates, z_coordinates = selenographic_to_cartesian(
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
        # Scatter3d draws text above its point by default, which would pull the
        # S towards the sphere; push each label away from the Moon instead.
        textposition=["middle center", "middle center", "top center", "bottom center"],
        textfont={"color": REFERENCE_COLOR, "family": "DM Mono, monospace", "size": 13},
        hoverinfo="skip",
    )
    return [equator, poles]


def _camera_eye(
    latitude: float, longitude: float, distance: float = CAMERA_DISTANCE
) -> dict[str, float]:
    x_coordinate, y_coordinate, z_coordinate = selenographic_to_cartesian(
        latitude, longitude, distance
    )
    return {
        "x": float(x_coordinate),
        "y": float(y_coordinate),
        "z": float(z_coordinate),
    }


def focus_camera(
    latitude: float, longitude: float, distance: float = CAMERA_DISTANCE
) -> dict[str, dict[str, float]]:
    """Plotly scene camera looking at a point, north up.

    Args:
        latitude: Latitude of the point to face, in degrees.
        longitude: Longitude of the point to face, in degrees.
        distance: Eye distance from the centre, in Plotly eye units (the
            starting view is ``CAMERA_DISTANCE``); keeps the current zoom.

    Returns:
        A ``scene.camera`` dict with ``eye``, ``center`` and ``up``.
    """
    return {
        "eye": _camera_eye(latitude, longitude, distance),
        "center": {"x": 0.0, "y": 0.0, "z": 0.0},
        "up": {"x": 0.0, "y": 0.0, "z": 1.0},
    }


def camera_distance(camera: dict | None) -> float | None:
    """Eye distance of a Plotly ``scene.camera`` dict, or ``None`` if unusable."""
    try:
        eye = camera["eye"]
        return math.sqrt(sum(float(eye[axis]) ** 2 for axis in ("x", "y", "z")))
    except (KeyError, TypeError, ValueError):
        return None


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
    show_labels: bool = True,
    camera: dict | None = None,
) -> go.Figure:
    """Build the globe with every visible tile and the selected frame on top.

    With ``show_labels``, each photo carries its frame ID at its centre and
    the selection's label is drawn in the accent colour above its marker.

    Args:
        selected: The frame shown in the side panel, drawn on top.
        tiles: The mission's photos.
        hidden: Frame IDs not to draw.
        show_labels: Whether to label each photo with its frame ID.
        camera: Plotly ``scene.camera`` to use, e.g. the user's current view;
            by default the camera faces the selection (or the first tile) from
            ``CAMERA_DISTANCE``. ``uirevision`` stays constant, so the view
            only moves when this camera changes.
    """
    tiles = sorted(tiles, key=lambda tile: tile.frame_id)
    images = visible_images(selected, tiles, hidden)
    mosaic = [image for image in images if image is not selected]
    traces: list[go.Surface | go.Mesh3d | go.Scatter3d] = [_base_sphere()]
    if mosaic:
        traces.append(_tiles_mesh(mosaic))
    if selected is not None and selected in images:
        traces.append(_image_surface(selected, SELECTED_RADIUS))
    outlines = _high_altitude_outlines(images)
    if outlines is not None:
        traces.append(outlines)
    labels = _frame_labels(images, selected.frame_id if selected else None)
    if show_labels and labels is not None:
        traces.append(labels)
    traces += _reference_marks()
    if selected is not None:
        traces.append(_marker(selected))
    if camera is None:
        facing = selected or (tiles[0] if tiles else None)
        camera = (
            focus_camera(facing.latitude, facing.longitude)
            if facing is not None
            else focus_camera(22, 35)
        )

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
        uirevision="globe",
        scene={
            "xaxis": hidden_axis,
            "yaxis": hidden_axis,
            "zaxis": hidden_axis,
            "aspectmode": "cube",
            "bgcolor": "rgba(0,0,0,0)",
            "camera": camera,
        },
    )
    return figure
