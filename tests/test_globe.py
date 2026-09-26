import numpy as np
import pytest

from orbiter.globe import (
    FALLBACK_PATCH_DEGREES,
    MAX_PATCH_DEGREES,
    GlobeImage,
    _to_cartesian,
    format_coordinates,
    image_at,
    make_globe,
    patch_contains,
    patch_width_degrees,
    visible_images,
)


def _image(frame_id="1041", latitude=3.3, longitude=39.15, altitude_km=256.43):
    return GlobeImage(
        frame_id=frame_id,
        latitude=latitude,
        longitude=longitude,
        altitude_km=altitude_km,
        texture=np.full((32, 24), 160, dtype=np.uint8),
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


def test_patch_width_scales_with_altitude_and_is_bounded():
    assert patch_width_degrees(None) == FALLBACK_PATCH_DEGREES
    assert patch_width_degrees(46) < patch_width_degrees(256.43)
    assert patch_width_degrees(256.43) == pytest.approx(6.34, abs=0.01)
    assert patch_width_degrees(1_000_000) == MAX_PATCH_DEGREES


def test_image_at_finds_the_clicked_patch():
    near, far = _image("1041"), _image("1100", latitude=-40, longitude=-120)
    x, y, z = _to_cartesian(3.5, 39.0, 1.003)

    assert image_at([near, far], x, y, z) is near
    assert image_at([far], x, y, z) is None


def test_image_at_prefers_the_nearest_centre_when_patches_overlap():
    first, second = _image("1041", longitude=39.0), _image("1042", longitude=41.0)
    x, y, z = _to_cartesian(3.3, 40.8)

    assert image_at([first, second], x, y, z) is second


def test_visible_images_skip_hidden_and_replace_tile_with_selection():
    selected = _image("1041")
    tiles = [_image("1041"), _image("1042"), _image("1043")]

    images = visible_images(selected, tiles, {"1043"})

    assert [image.frame_id for image in images] == ["1042", "1041"]
    assert images[-1] is selected


REFERENCES = {"equator", "poles"}


def _without_references(figure):
    return [trace for trace in figure.data if trace.name not in REFERENCES]


def test_make_globe_without_images_has_only_base_sphere():
    assert [trace.type for trace in _without_references(make_globe())] == ["surface"]


def test_make_globe_marks_poles_and_equator():
    traces = {trace.name: trace for trace in make_globe().data}

    assert list(traces["poles"].text) == ["", "", "N", "S"]
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
    assert len(mosaic.x) == 32 * 24
    assert len(mosaic.i) == 2 * 31 * 23
    assert int(np.max(mosaic.i)) < len(mosaic.x)
    assert selected.name == "1041"
    assert list(figure.data[-1].text) == ["1041"]
    assert figure.layout.uirevision == "1041"


def test_make_globe_keeps_marker_for_hidden_selection():
    figure = make_globe(_image("1041"), [], {"1041"})

    assert [trace.type for trace in _without_references(figure)] == [
        "surface",
        "scatter3d",
    ]


def test_make_globe_centres_camera_on_selection():
    figure = make_globe(_image(latitude=-80))

    assert figure.layout.scene.camera.eye.z < 0


def test_patch_contains_handles_the_180_degree_meridian():
    east_edge = _image("2001", latitude=0, longitude=179.5)

    assert patch_contains(east_edge, 0, -179.5)
    assert patch_contains(east_edge, 0, 180.5)
    assert not patch_contains(east_edge, 0, 0)
