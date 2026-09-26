from io import BytesIO

import numpy as np
import pytest
import requests
from dash import no_update
from PIL import Image

from orbiter import app as app_module
from orbiter.app import (
    TEXTURE_SIZE,
    describe_hidden,
    globe_image,
    hide_clicked_image,
    list_mission_frames,
    metadata_rows,
    poll_mosaic,
    render_globe,
    select_frame,
    update_frame,
)
from orbiter.catalog import MissionProgress
from orbiter.globe import GlobeImage, _to_cartesian
from orbiter.lpi import OrbiterFrame

UPDATE_FRAME_OUTPUTS = 5
STATUS_INDEX = 4


def _jpeg_bytes(size: tuple[int, int] = (48, 32)) -> bytes:
    image = Image.new("L", size, color=160)
    image_bytes = BytesIO()
    image.save(image_bytes, format="JPEG")
    return image_bytes.getvalue()


def _frame(latitude=3.3, image_size=(48, 32), frame_id="1041", **extra):
    return OrbiterFrame(
        frame_id=frame_id,
        mission="Lunar Orbiter 1",
        latitude=latitude,
        longitude=39.15,
        image_url=f"https://example.test/{frame_id}.jpg",
        image_bytes=_jpeg_bytes(image_size),
        **extra,
    )


def _tile(frame_id, latitude, longitude):
    return GlobeImage(
        frame_id=frame_id,
        latitude=latitude,
        longitude=longitude,
        altitude_km=100.0,
        texture=np.zeros((20, 16), dtype=np.uint8),
    )


class FakeLoader:
    def __init__(self, progress=None):
        self.started = []
        self._progress = progress or MissionProgress()

    def start(self, mission):
        self.started.append(mission)

    def progress(self, mission):
        return self._progress


@pytest.fixture
def loader(monkeypatch):
    fake = FakeLoader()
    monkeypatch.setattr(app_module, "LOADER", fake)
    return fake


def _row_values(rows) -> dict[str, str]:
    return {row.children[0].children: row.children[1].children for row in rows}


def test_globe_image_limits_texture_size():
    image = globe_image(_frame(image_size=(1200, 900)))

    assert image.texture.shape == (192, 256)
    assert max(image.texture.shape) <= max(TEXTURE_SIZE)


def test_update_frame_returns_all_outputs_on_success(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_frame", lambda frame_id: _frame())

    result = update_frame(1, 0, "1041")

    assert len(result) == UPDATE_FRAME_OUTPUTS
    selected, preview, rows, link, status = result
    assert selected == "1041"
    assert preview.startswith("data:image/jpeg;base64,")
    values = _row_values(rows)
    assert values["MISIÓN"] == "Lunar Orbiter 1"
    assert values["PUNTO PRINCIPAL"] == "3.30° N  /  39.15° E"
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
    assert result[STATUS_INDEX].startswith(prefix)
    assert all(
        value is no_update
        for index, value in enumerate(result)
        if index != STATUS_INDEX
    )


def test_render_globe_combines_selection_and_mission_tiles(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_frame", lambda frame_id: _frame())
    tiles = {"1005": _tile("1005", 0, 0), "1006": _tile("1006", 10, 10)}
    monkeypatch.setattr(app_module, "LOADER", FakeLoader(MissionProgress(tiles=tiles)))

    figure = render_globe("1041", ["1006"], 2, 1)

    assert [trace.name for trace in figure.data[1:-1]] == ["1005", "1041"]


def test_metadata_rows_show_spacecraft_and_illumination():
    frame = _frame(
        spacecraft_altitude_km=256.43,
        spacecraft_latitude=4.29,
        spacecraft_longitude=41.17,
        sun_azimuth=88.76,
        incidence_angle=85.53,
        emission_angle=16.95,
        phase_angle=70.22,
    )

    values = _row_values(metadata_rows(frame))

    assert values["ALTITUD DE LA NAVE"] == "256.43 km"
    assert values["POSICIÓN DE LA NAVE"] == "4.29° N  /  41.17° E"
    assert values["ACIMUT SOLAR"] == "88.76°"
    assert values["INCIDENCIA / EMISIÓN"] == "85.53°  /  16.95°"
    assert values["ÁNGULO DE FASE"] == "70.22°"


def test_metadata_rows_mark_missing_fields():
    values = _row_values(metadata_rows(_frame()))

    assert values["ALTITUD DE LA NAVE"] == "—"
    assert values["POSICIÓN DE LA NAVE"] == "—"
    assert values["INCIDENCIA / EMISIÓN"] == "—"


def test_list_mission_frames_starts_mosaic(monkeypatch, loader):
    monkeypatch.setattr(app_module, "fetch_mission_frames", lambda m: ["1005", "1006"])

    options, value, disabled, status, poll_off, count, hidden = list_mission_frames(1)

    assert (options, value, disabled) == (["1005", "1006"], None, False)
    assert status == "MISIÓN 1 · 2 FOTOGRAMAS"
    assert (poll_off, count, hidden) == (False, 0, [])
    assert loader.started == [1]


def test_list_mission_frames_reports_connection_error(monkeypatch, loader):
    def fail(mission):
        raise requests.Timeout("lento")

    monkeypatch.setattr(app_module, "fetch_mission_frames", fail)

    options, value, disabled, status, poll_off, *_ = list_mission_frames(2)

    assert (options, value, disabled, poll_off) == ([], None, True, True)
    assert status.startswith("ERROR DE CONEXIÓN")
    assert loader.started == []


def test_poll_mosaic_rerenders_in_steps_and_stops_when_finished(monkeypatch):
    tiles = {str(index): _tile(str(index), 0, 0) for index in range(30)}
    fake = FakeLoader(MissionProgress(total=200, tiles=tiles))
    monkeypatch.setattr(app_module, "LOADER", fake)

    status, count, poll_off = poll_mosaic(1, 1, 0)
    assert (status, count, poll_off) == ("DESCARGANDO MOSAICO · 30/200", 30, False)
    assert poll_mosaic(2, 1, 30)[1] is no_update

    fake._progress = MissionProgress(total=31, failed=1, finished=True, tiles=tiles)
    status, count, poll_off = poll_mosaic(3, 1, 30)
    assert status == "MOSAICO · 30 FOTOS EN LA ESFERA · 1 SIN DATOS"
    assert (count, poll_off) == (no_update, True)


def test_hide_clicked_image_hides_and_selects_tile(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_frame", lambda frame_id: _frame())
    tiles = {"1100": _tile("1100", -40, -120)}
    monkeypatch.setattr(app_module, "LOADER", FakeLoader(MissionProgress(tiles=tiles)))
    x, y, z = _to_cartesian(-40.2, -120.1, 1.003)
    click = {"points": [{"x": x, "y": y, "z": z, "curveNumber": 1}]}

    assert hide_clicked_image(click, ["1005"], "1041", 1) == (["1005", "1100"], "1100")


def test_hide_clicked_image_ignores_clicks_outside_photos(monkeypatch, loader):
    monkeypatch.setattr(app_module, "fetch_frame", lambda frame_id: _frame())
    x, y, z = _to_cartesian(-60, 150)
    click = {"points": [{"x": x, "y": y, "z": z}]}

    assert hide_clicked_image(click, [], "1041", 1) == (no_update, no_update)
    assert hide_clicked_image(None, [], "1041", 1) == (no_update, no_update)


def test_describe_hidden_counts_and_disables_button():
    assert describe_hidden(["1005", "1006"]) == ("MOSTRAR OCULTAS (2)", False)
    assert describe_hidden([]) == ("MOSTRAR OCULTAS (0)", True)


def test_select_frame_loads_and_unhides_frame():
    assert select_frame("1006", ["1005", "1006"]) == ("1006", ["1005"])
    assert select_frame(None, ["1005"]) == (no_update, no_update)
