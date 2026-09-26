import base64
from io import BytesIO

import pytest
import requests
from dash import no_update
from PIL import Image

from orbiter import app as app_module
from orbiter.app import format_coordinates, make_globe, rotate_globe, update_frame
from orbiter.lpi import OrbiterFrame

UPDATE_FRAME_OUTPUTS = 8


def _jpeg_bytes() -> bytes:
    image = Image.new("L", (48, 32), color=160)
    image_bytes = BytesIO()
    image.save(image_bytes, format="JPEG")
    return image_bytes.getvalue()


def _frame() -> OrbiterFrame:
    return OrbiterFrame(
        frame_id="1041",
        mission="Lunar Orbiter 1",
        latitude=3.3,
        longitude=39.15,
        image_url="https://example.test/1041.jpg",
        image_bytes=_jpeg_bytes(),
    )


def _decode_png(data_url: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(data_url.split(",", 1)[1])))


def test_make_globe_renders_frame_as_png():
    rendered = make_globe(_frame(), azimuth=60, elevation=25)
    rendered_image = _decode_png(rendered)

    assert rendered.startswith("data:image/png;base64,")
    assert rendered_image.format == "PNG"
    assert rendered_image.width > 300
    assert rendered_image.height > 300


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
    globe, preview, mission, center, frame_id, link, status, data = result
    assert globe.startswith("data:image/png;base64,")
    assert preview.startswith("data:image/jpeg;base64,")
    assert mission == "Lunar Orbiter 1"
    assert center == "3.30° N  /  39.15° E"
    assert frame_id == "1041"
    assert link.endswith("/frame/?1041")
    assert "1041" in status
    assert data["frame_id"] == "1041"
    assert rotate_globe(10, 20, data).startswith("data:image/png;base64,")


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


def test_rotate_globe_without_frame():
    assert rotate_globe(0, 0, None).startswith("data:image/png;base64,")
