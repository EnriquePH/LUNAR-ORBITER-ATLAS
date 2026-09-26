import math
import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from orbiter.globe import (
    ACCENT,
    CAMERA_DISTANCE,
    FALLBACK_PATCH_DEGREES,
    MAX_PATCH_DEGREES,
    MAX_TILE_PIXELS,
    MESH_VERTEX_BUDGET,
    MIN_TILE_PIXELS,
    MOON_RADIUS_KM,
    GlobeImage,
    _patch_grid,
    _rolled,
    camera_distance,
    camera_of,
    cartesian_to_selenographic,
    focus_camera,
    footprint_outline,
    format_coordinates,
    frame_camera,
    frame_geometry,
    image_at,
    implied_emission_angle,
    make_globe,
    patch_contains,
    patch_width_degrees,
    selenographic_to_cartesian,
    tile_textures,
    visible_images,
)


def _image(
    frame_id="1041", latitude=3.3, longitude=39.15, altitude_km=256.43, size=(32, 24)
):
    return GlobeImage(
        frame_id=frame_id,
        latitude=latitude,
        longitude=longitude,
        altitude_km=altitude_km,
        texture=np.full(size, 160, dtype=np.uint8),
    )


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [
        (3.3, 39.15, "3.30° N  /  39.15° E"),
        (-3.2, -23.5, "3.20° S  /  23.50° W"),
        (0.0, 0.0, "0.00° N  /  0.00° E"),
    ],
)
def test_format_coordinates_uses_hemispheres(latitude, longitude, expected):
    assert format_coordinates(latitude, longitude) == expected


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(0, 0), (3.3, 39.15), (-40.2, -120.1), (89.5, 179.9), (-89.5, -179.9)],
)
def test_coordinate_conversion_round_trips(latitude, longitude):
    x, y, z = selenographic_to_cartesian(latitude, longitude, 1.2)
    assert math.isclose(math.hypot(x, y, z), 1.2)
    back = cartesian_to_selenographic(x, y, z)
    assert back == pytest.approx((latitude, longitude))


def test_coordinate_conversion_axes_and_wrapped_longitudes():
    assert selenographic_to_cartesian(0, 0) == pytest.approx((1, 0, 0))
    assert selenographic_to_cartesian(0, 90) == pytest.approx((0, 1, 0), abs=1e-12)
    assert selenographic_to_cartesian(90, 0) == pytest.approx((0, 0, 1), abs=1e-12)
    assert cartesian_to_selenographic(*selenographic_to_cartesian(10, 190)) == (
        pytest.approx((10, -170))
    )


def test_coordinate_conversion_accepts_arrays():
    latitudes, longitudes = np.array([[0.0, 45.0]]), np.array([[30.0, -60.0]])
    x, y, z = selenographic_to_cartesian(latitudes, longitudes)
    assert x.shape == y.shape == z.shape == (1, 2)
    assert np.allclose(x**2 + y**2 + z**2, 1.0)


def test_patch_width_scales_with_altitude_and_is_bounded():
    assert patch_width_degrees(None) == FALLBACK_PATCH_DEGREES
    assert patch_width_degrees(46) < patch_width_degrees(256.43)
    assert patch_width_degrees(256.43) == pytest.approx(6.34, abs=0.01)
    assert patch_width_degrees(1_000_000) == MAX_PATCH_DEGREES


def test_image_at_finds_the_clicked_patch():
    near, far = _image("1041"), _image("1100", latitude=-40, longitude=-120)
    x, y, z = selenographic_to_cartesian(3.5, 39.0, 1.003)

    assert image_at([near, far], x, y, z) is near
    assert image_at([far], x, y, z) is None


def test_image_at_prefers_the_nearest_centre_when_patches_overlap():
    first, second = _image("1041", longitude=39.0), _image("1042", longitude=41.0)
    x, y, z = selenographic_to_cartesian(3.3, 40.8)

    assert image_at([first, second], x, y, z) is second


def test_visible_images_skip_hidden_and_replace_tile_with_selection():
    selected = _image("1041")
    tiles = [_image("1041"), _image("1042"), _image("1043")]

    images = visible_images(selected, tiles, {"1043"})

    assert [image.frame_id for image in images] == ["1042", "1041"]
    assert images[-1] is selected


REFERENCES = {"equator", "poles", "labels"}


def _without_references(figure):
    return [trace for trace in figure.data if trace.name not in REFERENCES]


def test_make_globe_without_images_has_only_base_sphere():
    assert [trace.type for trace in _without_references(make_globe())] == ["surface"]


def test_make_globe_marks_poles_and_equator():
    traces = {trace.name: trace for trace in make_globe().data}

    assert list(traces["poles"].text) == ["", "", "N", "S"]
    assert list(traces["poles"].textposition)[2:] == ["top center", "bottom center"]
    assert list(traces["poles"].z) == [1.01, -1.01, 1.18, -1.18]
    assert np.allclose(traces["equator"].z, 0)
    assert traces["equator"].hoverinfo == traces["poles"].hoverinfo == "skip"


def test_make_globe_draws_tiles_selection_and_marker():
    figure = make_globe(_image("1041"), [_image("1042"), _image("1043")], {"1043"})

    base, mosaic, selected, marker = _without_references(figure)
    assert (mosaic.type, selected.type, marker.type) == (
        "mesh3d",
        "surface",
        "scatter3d",
    )
    assert set(np.asarray(mosaic.customdata)) == {1042}
    # A 6.3° patch gets 19 px on its long side: a 19 × 14 vertex grid.
    assert len(mosaic.x) == 19 * 14
    assert len(mosaic.i) == 2 * 18 * 13
    assert np.asarray(mosaic.intensity).dtype == np.uint8
    assert int(np.max(mosaic.i)) < len(mosaic.x)
    assert selected.name == "1041"
    assert figure.data[-1].marker.color == ACCENT
    assert figure.layout.uirevision == "globe"


def test_make_globe_labels_each_photo_at_its_centre():
    figure = make_globe(_image("1041"), [_image("1042", latitude=10, longitude=-20)])

    (labels,) = [trace for trace in figure.data if trace.name == "labels"]
    assert list(labels.text) == ["1042", "1041"]
    assert labels.hoverinfo == "skip"
    point = (labels.x[0], labels.y[0], labels.z[0])
    assert cartesian_to_selenographic(*point) == pytest.approx((10, -20))


def test_make_globe_highlights_the_selected_label():
    figure = make_globe(_image("1041"), [_image("1042"), _image("1041")])

    (labels,) = [trace for trace in figure.data if trace.name == "labels"]
    colors = dict(zip(labels.text, labels.textfont.color, strict=True))
    assert colors["1041"] == ACCENT
    assert colors["1042"] != ACCENT
    assert list(labels.text).count("1041") == 1


def test_make_globe_can_hide_labels():
    figure = make_globe(_image("1041"), [_image("1042")], show_labels=False)

    assert all(trace.name != "labels" for trace in figure.data)
    assert figure.data[-1].marker.color == ACCENT  # the selection keeps its dot


def test_make_globe_without_photos_has_no_labels():
    assert all(trace.name != "labels" for trace in make_globe().data)


def test_make_globe_keeps_marker_for_hidden_selection():
    figure = make_globe(_image("1041"), [], {"1041"})

    assert [trace.type for trace in _without_references(figure)] == [
        "surface",
        "scatter3d",
    ]


def test_make_globe_uses_the_given_camera():
    camera = focus_camera(0, 90, 0.7)

    figure = make_globe(_image(), camera=camera)

    eye = figure.layout.scene.camera.eye
    assert (eye.x, eye.y, eye.z) == pytest.approx((0, 0.7, 0), abs=1e-12)


def test_camera_distance_reads_the_eye_or_gives_none():
    assert camera_distance(focus_camera(10, 20, 1.3)) == pytest.approx(1.3)
    assert camera_distance({"up": {}}) is None
    assert camera_distance(None) is None


def test_make_globe_centres_camera_on_selection():
    figure = make_globe(_image(latitude=-80))

    assert figure.layout.scene.camera.eye.z < 0


def test_patch_contains_handles_the_180_degree_meridian():
    east_edge = _image("2001", latitude=0, longitude=179.5)

    assert patch_contains(east_edge, 0, -179.5)
    assert patch_contains(east_edge, 0, 180.5)
    assert not patch_contains(east_edge, 0, 0)


def test_tile_textures_scale_with_patch_size():
    small = _image("1001", altitude_km=50, size=(48, 41))
    large = _image("4001", altitude_km=3000, size=(48, 41))

    small_texture, large_texture = tile_textures([small, large])

    assert max(small_texture.shape) == MIN_TILE_PIXELS
    assert max(large_texture.shape) == MAX_TILE_PIXELS


def test_tile_textures_never_enlarge():
    (texture,) = tile_textures([_image(altitude_km=3000, size=(12, 10))])

    assert texture.shape == (12, 10)


def test_tile_textures_respect_the_vertex_budget():
    tiles = [
        _image(str(4000 + index), altitude_km=3000, size=(48, 41))
        for index in range(200)
    ]

    textures = tile_textures(tiles)

    assert sum(texture.size for texture in textures) <= MESH_VERTEX_BUDGET
    assert max(textures[0].shape) < MAX_TILE_PIXELS


def _projected(
    latitude=3.30, longitude=39.15, altitude_km=256.43, spacecraft=(4.29, 41.17)
):
    return GlobeImage(
        frame_id="1041",
        latitude=latitude,
        longitude=longitude,
        altitude_km=altitude_km,
        texture=np.full((65, 55), 160, dtype=np.uint8),
        spacecraft_latitude=spacecraft[0],
        spacecraft_longitude=spacecraft[1],
    )


def _arc_km(first, second):
    return math.acos(np.clip(first @ second, -1, 1)) * MOON_RADIUS_KM


def test_projection_matches_the_documented_nadir_footprint():
    x, y, z = _patch_grid(_projected(0, 0, 46, (0, 0)), 1.0)
    points = np.stack([x, y, z], axis=-1)

    # 31.6 x 37.4 km from 46 km for the medium-resolution camera.
    assert _arc_km(points[32, 0], points[32, -1]) == pytest.approx(31.6, abs=0.3)
    assert _arc_km(points[0, 27], points[-1, 27]) == pytest.approx(37.4, abs=0.3)


def test_projection_centres_an_oblique_frame_on_its_principal_point():
    x, y, z = _patch_grid(_projected(), 1.0)

    latitude, longitude = cartesian_to_selenographic(x[32, 27], y[32, 27], z[32, 27])
    assert (latitude, longitude) == pytest.approx((3.30, 39.15), abs=1e-6)


def test_projection_drops_pixels_that_miss_the_moon():
    x, _, _ = _patch_grid(_projected(0, 40, 1500, (0, 0)), 1.0)

    assert 0 < np.isnan(x).sum() < x.size


def test_frames_without_spacecraft_position_use_the_fallback_patch():
    assert frame_camera(_image()) is None
    assert frame_camera(_projected()) is not None


def test_projected_frames_answer_clicks_by_what_the_camera_saw():
    frame = _projected()

    assert patch_contains(frame, 3.30, 39.15)
    assert not patch_contains(frame, 3.30, 60.0)
    assert not patch_contains(frame, -3.30, -140.85)  # far side


def test_mesh_skips_triangles_off_the_moon_and_outlines_high_frames():
    oblique = _projected(0, 40, 1500, (0, 0))
    figure = make_globe(None, [oblique], ())
    traces = {trace.name: trace for trace in figure.data}
    mesh = next(trace for trace in figure.data if trace.type == "mesh3d")

    faces = np.stack([mesh.i, mesh.j, mesh.k], axis=1)
    x = np.asarray(mesh.x)
    assert len(faces) < 2 * (x.size - 1)
    assert np.isfinite(x).all()
    assert "high-altitude" in traces
    assert oblique.is_high_altitude
    assert not _projected().is_high_altitude


def test_inconsistent_metadata_falls_back_to_the_patch():
    hidden_point = _projected(0, 60, 1500, (0, 0))  # past the limb
    consistent = replace(_projected(), emission_angle=16.95)
    contradicted = replace(_projected(), emission_angle=60.0)

    assert frame_camera(hidden_point) is None
    assert frame_camera(consistent) is not None
    assert frame_camera(contradicted) is None


def test_camera_of_reads_the_preview_kind():
    assert camera_of("https://x/images/preview/1041_med.jpg") == "medium"
    assert camera_of("https://x/images/preview/4100_h2.jpg") == "high"


def test_high_resolution_camera_sees_a_narrower_field():
    medium = frame_camera(_projected(0, 0, 2900, (0, 0)))
    high = frame_camera(replace(_projected(0, 0, 2900, (0, 0)), camera="high"))

    assert high.half_width == pytest.approx(medium.half_width * 80 / 610)


def test_oblique_frames_are_level_with_the_horizon_up():
    camera = frame_camera(_projected(0, 30, 100, (0, 33)))  # looking west
    target = np.array(selenographic_to_cartesian(0, 30))

    assert camera.up @ target > 0.5


def test_high_altitude_frames_roll_to_match_a_black_sky():
    frame = _projected(0, 40, 1500, (0, 0))
    base = frame_camera(frame)
    rolled = _rolled(base, 1)
    height, width = frame.texture.shape
    horizontal, vertical = np.meshgrid(
        np.linspace(-rolled.half_width, rolled.half_width, width),
        np.linspace(rolled.half_height, -rolled.half_height, height),
    )
    _, on_moon = rolled.hit_sphere(rolled.rays(horizontal, vertical))
    texture = np.where(on_moon, 170, 5).astype(np.uint8)

    camera = frame_camera(replace(frame, frame_id="sky", texture=texture))

    assert np.allclose(camera.up, rolled.up)
    low = replace(frame, frame_id="low", altitude_km=900.0, texture=texture)
    assert not np.allclose(frame_camera(low).up, _rolled(frame_camera(low), 1).up)


def test_frame_geometry_measures_the_projected_footprint():
    geometry = frame_geometry(_projected(0, 0, 46, (0, 0)))

    assert geometry.projected
    assert geometry.width_km == pytest.approx(31.6, abs=0.3)
    assert geometry.height_km == pytest.approx(37.4, abs=0.3)
    assert geometry.implied_emission == pytest.approx(0.0, abs=1e-6)


def test_frame_geometry_counts_only_ground_seen_past_the_limb():
    geometry = frame_geometry(_projected(0, 40, 1500, (0, 0)))

    # Wider than a nadir view, but never more than the visible hemisphere.
    assert 500 < geometry.width_km < math.pi * MOON_RADIUS_KM


def test_frame_geometry_falls_back_to_the_approximate_patch():
    geometry = frame_geometry(_image(altitude_km=46.0, size=(32, 24)))

    assert not geometry.projected
    assert geometry.implied_emission is None
    assert geometry.height_km == pytest.approx(geometry.width_km * 32 / 24)


def test_implied_emission_matches_the_lpi_value_for_frame_1041():
    # LPI: emission 16.95° for frame 1041.
    assert implied_emission_angle(_projected()) == pytest.approx(16.95, abs=0.35)


def test_footprint_outline_of_a_whole_disc_shot_follows_the_limb():
    # From 5500 km the 80 mm frame is wider than the Moon: no edge touches it.
    image = replace(_projected(0, 0, 5500, (0, 0)), texture=np.zeros((65, 55)))

    outline = footprint_outline(image)

    # The visible cap reaches acos(R / (R + h)) ≈ 76.1° from the centre.
    limb = math.degrees(math.acos(MOON_RADIUS_KM / (MOON_RADIUS_KM + 5500)))
    distances = [
        math.degrees(
            math.acos(math.cos(math.radians(lat)) * math.cos(math.radians(lon)))
        )
        for lat, lon in outline
    ]
    assert len(outline) > 20
    assert min(distances) == pytest.approx(limb, abs=0.1)
    assert max(distances) <= limb + 1e-6


def test_rotation_script_starts_from_the_globe_camera_distance():
    script = (
        Path(__file__).parents[1] / "orbiter" / "assets" / "rotation.js"
    ).read_text()

    match = re.search(r"FULL_SPEED_DISTANCE = ([\d.]+);", script)
    assert match is not None
    assert float(match.group(1)) == CAMERA_DISTANCE
