"""Export a mission's frames: metadata as CSV and footprints as GeoJSON.

Both exports cover the frames loaded on the globe. Coordinates are
selenographic degrees (north and east positive), not WGS 84: GeoJSON readers
treat them as plain longitude/latitude pairs, which is what a lunar map needs.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Iterable, Mapping

from orbiter.globe import GlobeImage, footprint_outline, frame_geometry
from orbiter.lpi import FrameMetadata

CSV_FIELDS = (
    "frame_id",
    "mission",
    "latitude",
    "longitude",
    "spacecraft_altitude_km",
    "spacecraft_latitude",
    "spacecraft_longitude",
    "sun_azimuth",
    "incidence_angle",
    "emission_angle",
    "phase_angle",
    "camera",
    "footprint_width_km",
    "footprint_height_km",
    "projected",
    "implied_emission_angle",
    "image_url",
)


def _rounded(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def mission_csv(
    images: Iterable[GlobeImage],
    metadata: Callable[[str], FrameMetadata | None] | Mapping[str, FrameMetadata],
) -> str:
    """Build a CSV table with one row per frame, sorted by frame ID.

    Args:
        images: The mission's globe images.
        metadata: LPI page metadata by frame ID, as a mapping or a lookup
            function; frames without it keep the fields their image carries.

    Returns:
        CSV text with the ``CSV_FIELDS`` columns; unknown values are empty.
        Footprints are in km and angles in degrees.
    """
    lookup = metadata.get if isinstance(metadata, Mapping) else metadata
    output = io.StringIO()
    writer = csv.DictWriter(output, CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for image in sorted(images, key=lambda image: int(image.frame_id)):
        geometry = frame_geometry(image)
        row: dict[str, object] = {
            "latitude": image.latitude,
            "longitude": image.longitude,
            "spacecraft_altitude_km": image.altitude_km,
            "spacecraft_latitude": image.spacecraft_latitude,
            "spacecraft_longitude": image.spacecraft_longitude,
            "emission_angle": image.emission_angle,
            **(lookup(image.frame_id) or {}),
        }
        row.update(
            frame_id=image.frame_id,
            camera=image.camera,
            footprint_width_km=round(geometry.width_km, 2),
            footprint_height_km=round(geometry.height_km, 2),
            projected=geometry.projected,
            implied_emission_angle=_rounded(geometry.implied_emission, 3),
        )
        writer.writerow({key: row.get(key) for key in CSV_FIELDS})
    return output.getvalue()


def _ring(outline: list[tuple[float, float]]) -> list[list[float]]:
    """Close an outline as a GeoJSON ring, with continuous longitudes.

    Longitudes are unwrapped from the first point, so a frame that crosses the
    180° meridian stays one polygon (some of its longitudes exceed ±180). A
    frame around a pole winds through 360°; its ring is closed along the pole
    (latitude ±90). The ring runs counterclockwise, as RFC 7946 asks of
    exterior rings.
    """
    ring: list[list[float]] = []
    for latitude, longitude in outline:
        if ring:
            longitude += round((ring[-1][0] - longitude) / 360) * 360
        ring.append([longitude, latitude])
    first, last = ring[0], ring[-1]
    closing = first[0] + round((last[0] - first[0]) / 360) * 360
    if closing != first[0]:  # the outline went once round a pole
        pole = 90.0 if sum(point[1] for point in ring) > 0 else -90.0
        ring += [[closing, first[1]], [closing, pole], [first[0], pole]]
    ring = [[round(longitude, 5), round(latitude, 5)] for longitude, latitude in ring]
    doubled_area = sum(
        x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1])
    )
    if doubled_area < 0:
        ring.reverse()
    ring.append(ring[0])
    return ring


def footprints_geojson(images: Iterable[GlobeImage]) -> str:
    """Build a GeoJSON ``FeatureCollection`` of frame footprints.

    Each feature is a ``Polygon`` from :func:`footprint_outline` with the
    frame ID, principal point, altitude (km), camera and footprint size (km)
    as properties. Frames whose outline has fewer than three points are
    skipped.

    Returns:
        The collection as JSON text.
    """
    features = []
    for image in sorted(images, key=lambda image: int(image.frame_id)):
        outline = footprint_outline(image)
        if len(outline) < 3:
            continue
        geometry = frame_geometry(image)
        features.append(
            {
                "type": "Feature",
                "id": image.frame_id,
                "geometry": {"type": "Polygon", "coordinates": [_ring(outline)]},
                "properties": {
                    "frame_id": image.frame_id,
                    "latitude": image.latitude,
                    "longitude": image.longitude,
                    "altitude_km": image.altitude_km,
                    "camera": image.camera,
                    "footprint_width_km": round(geometry.width_km, 2),
                    "footprint_height_km": round(geometry.height_km, 2),
                    "projected": geometry.projected,
                },
            }
        )
    return json.dumps({"type": "FeatureCollection", "features": features})
