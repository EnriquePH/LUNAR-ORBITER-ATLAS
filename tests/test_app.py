from io import BytesIO

import pytest
import requests
from dash import no_update
from PIL import Image

from orbiter import app as app_module
from orbiter.app import TEXTURE_SIZE, format_coordinates, make_globe, update_frame
from orbiter.lpi import OrbiterFrame

UPDATE_FRAME_OUTPUTS = 7


def _jpeg_bytes(size: tuple[int, int] = (48, 32)) -> bytes:
    image = Image.new("L", size, color=160)
    image_bytes = BytesIO()
    image.save(image_bytes, format="JPEG")
    return image_bytes.getvalue()


def _frame(latitude: float = 3.3, image_size: tuple[int, int] = (48, 32)):
    return OrbiterFrame(
        frame_id="1041",
        mission="Lunar Orbiter 1",
        latitude=latitude,
        longitude=39.15,
        image_url="https://example.test/1041.jpg",
        image_bytes=_jpeg_bytes(image_size),
    )


def test_make_globe_without_frame_has_only_base_sphere():
    figure = make_globe()

    assert [trace.type for trace in figure.data] == ["surface"]


def test_make_globe_adds_textured_patch_and_marker():
    figure = make_globe(_frame())

    base, patch, marker = figure.data
    assert (base.type, patch.type, marker.type) == ("surface", "surface", "scatter3d")
    assert patch.surfacecolor.shape == (32, 48)
    assert list(marker.text) == ["1041"]


def test_make_globe_limits_texture_size_and_centres_camera():
    figure = make_globe(_frame(latitude=-80, image_size=(1200, 900)))

    patch = figure.data[1]
    assert max(patch.surfacecolor.shape) <= max(TEXTURE_SIZE)
    assert patch.z.min() >= -1.01
    assert figure.layout.scene.camera.eye.z < 0


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


def test_update_frame_returns_all_outputs_on_success(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_frame", lambda frame_id: _frame())

    result = update_frame(1, 0, "1041")

    assert len(result) == UPDATE_FRAME_OUTPUTS
    globe, preview, mission, center, frame_id, link, status = result
    assert len(globe.data) == 3
    assert preview.startswith("data:image/jpeg;base64,")
    assert mission == "Lunar Orbiter 1"
    assert center == "3.30° N  /  39.15° E"
    assert frame_id == "1041"
    assert link.endswith("/frame/?1041")
    assert "1041" in status


@pytest.mark.parametrize(
    ("error", "prefix"),
    [
        (ValueError("ID inválido"), "NO SE PUDO CARGAR"),
        (requests.ConnectionError("sin red"), "ERROR DE CONEXIÓN"),
    ],
)
def test_update_frame_reports_errors_without_changing_view(monkeypatch, error, prefix):
    def fail(frame_id):
        raise error

    monkeypatch.setattr(app_module, "fetch_frame", fail)

    result = update_frame(1, 0, "x")

    assert len(result) == UPDATE_FRAME_OUTPUTS
    assert result[6].startswith(prefix)
    assert all(value is no_update for index, value in enumerate(result) if index != 6)
