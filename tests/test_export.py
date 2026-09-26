import csv
import io
import json

import numpy as np
import pytest

from orbiter.export import CSV_FIELDS, footprints_geojson, mission_csv
from orbiter.globe import GlobeImage


def _image(frame_id="1041", longitude=39.15, spacecraft=(4.29, 41.17), **extra):
    return GlobeImage(
        frame_id=frame_id,
        latitude=3.30,
        longitude=longitude,
        altitude_km=256.43,
        texture=np.full((65, 55), 160, dtype=np.uint8),
        spacecraft_latitude=spacecraft[0],
        spacecraft_longitude=spacecraft[1],
        **extra,
    )


def _rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_mission_csv_merges_cached_metadata_and_geometry():
    metadata = {"1041": {"mission": "Lunar Orbiter 1", "sun_azimuth": 88.76}}

    rows = _rows(mission_csv([_image("1042"), _image("1041")], metadata))

    assert list(rows[0]) == list(CSV_FIELDS)
    assert [row["frame_id"] for row in rows] == ["1041", "1042"]
    assert rows[0]["mission"] == "Lunar Orbiter 1"
    assert rows[0]["sun_azimuth"] == "88.76"
    assert rows[1]["mission"] == ""
    assert rows[1]["spacecraft_altitude_km"] == "256.43"
    assert rows[0]["projected"] == "True"
    assert float(rows[0]["implied_emission_angle"]) == pytest.approx(17.04, abs=0.01)
    assert float(rows[0]["footprint_width_km"]) > 0


def test_mission_csv_accepts_a_lookup_function():
    rows = _rows(mission_csv([_image()], lambda frame_id: None))

    assert rows[0]["frame_id"] == "1041"


def test_footprints_geojson_has_closed_counterclockwise_polygons():
    collection = json.loads(footprints_geojson([_image()]))

    (feature,) = collection["features"]
    ring = feature["geometry"]["coordinates"][0]
    assert collection["type"] == "FeatureCollection"
    assert feature["properties"]["frame_id"] == "1041"
    assert ring[0] == ring[-1]
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:]))
    assert area > 0
    longitudes = [point[0] for point in ring]
    assert min(longitudes) < 39.15 < max(longitudes)


def test_footprints_geojson_keeps_frames_across_180_degrees_in_one_piece():
    collection = json.loads(
        footprints_geojson([_image(longitude=179.9, spacecraft=(4.29, -178.0))])
    )

    ring = collection["features"][0]["geometry"]["coordinates"][0]
    longitudes = [point[0] for point in ring]
    assert max(longitudes) - min(longitudes) < 20


def test_footprints_geojson_closes_rings_around_a_pole():
    # High over 60° N with the pole in view, as Lunar Orbiter 5 frame 5011.
    polar = GlobeImage(
        frame_id="5011",
        latitude=80.0,
        longitude=0.0,
        altitude_km=2600.0,
        texture=np.full((65, 55), 160, dtype=np.uint8),
        spacecraft_latitude=80.0,
        spacecraft_longitude=0.0,
    )

    collection = json.loads(footprints_geojson([polar]))

    ring = collection["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    assert max(point[1] for point in ring) == 90.0
    longitudes = [point[0] for point in ring]
    assert max(longitudes) - min(longitudes) == pytest.approx(360, abs=10)
