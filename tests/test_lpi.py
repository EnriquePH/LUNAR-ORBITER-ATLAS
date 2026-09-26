from types import SimpleNamespace

import pytest

from orbiter.lpi import (
    LpiError,
    fetch_frame,
    fetch_mission_frames,
    parse_frame_page,
    parse_mission_page,
)

FRAME_PAGE = """
<table>
  <tr><td>Mission:</td><td>Lunar Orbiter 1</td></tr>
  <tr><td>Principal Point:</td><td>Latitude:</td><td>3.30°</td>
      <td>Longitude:</td><td>39.15°</td></tr>
</table>
<a href="../images/preview/1041_med.jpg">medium</a>
"""

# Mirrors the layout of the live LPI frame table, including the &nbsp; spacing.
FULL_FRAME_PAGE = """
<table><tr><td>
Mission: Lunar Orbiter 1<br>
Spacecraft Position:<br>
&nbsp; Altitude: 256.43 km &nbsp; Latitude: 4.29° &nbsp; Longitude: 41.17°<br>
Principal Point:<br>
&nbsp; Latitude: 3.30° &nbsp; Longitude: -39.15°<br>
Illumination:<br>
&nbsp; Sun Azimuth: 88.76° &nbsp; Incident Angle: 85.53°
&nbsp; Emission Angle: 16.95° &nbsp; Phase Angle: 70.22° &nbsp; Alpha: 15.27°<br>
Hi Resolution Plates(s):<br>
&nbsp; 1041_h1 <a href="../images/preview/1041_h1.jpg">Preview JPG</a>
&nbsp; 1041_med <a href="../images/preview/1041_med.jpg">Preview JPG</a>
</td></tr></table>
"""

MISSION_PAGE = """
<a href="../">Gallery</a>
<a class="thumbnail-link" href="../frame/?1005"><img alt="1005"></a>
<a class="thumbnail-link" href="../frame/?1006"><img alt="1006"></a>
<a href="../frame/?1005">duplicate</a>
"""


def test_parse_frame_page_resolves_relative_preview_url():
    metadata = parse_frame_page("1041", FRAME_PAGE)

    assert metadata == {
        "mission": "Lunar Orbiter 1",
        "latitude": 3.3,
        "longitude": 39.15,
        "image_url": "https://www.lpi.usra.edu/resources/lunarorbiter/images/preview/1041_med.jpg",
        "spacecraft_altitude_km": None,
        "spacecraft_latitude": None,
        "spacecraft_longitude": None,
        "sun_azimuth": None,
        "incidence_angle": None,
        "emission_angle": None,
        "phase_angle": None,
    }


def test_parse_frame_page_reads_spacecraft_and_illumination():
    metadata = parse_frame_page("1041", FULL_FRAME_PAGE)

    assert metadata["latitude"] == 3.3
    assert metadata["longitude"] == -39.15
    assert metadata["spacecraft_altitude_km"] == 256.43
    assert metadata["spacecraft_latitude"] == 4.29
    assert metadata["spacecraft_longitude"] == 41.17
    assert metadata["sun_azimuth"] == 88.76
    assert metadata["incidence_angle"] == 85.53
    assert metadata["emission_angle"] == 16.95
    assert metadata["phase_angle"] == 70.22
    assert metadata["image_url"].endswith("/1041_med.jpg")


def test_parse_mission_page_lists_unique_frames_in_order():
    assert parse_mission_page(MISSION_PAGE) == ["1005", "1006"]


@pytest.mark.parametrize("mission", [0, 6])
def test_fetch_mission_frames_rejects_unknown_mission(monkeypatch, mission):
    monkeypatch.setattr(
        "orbiter.lpi.requests.get", lambda *a, **k: pytest.fail("sin red")
    )

    with pytest.raises(LpiError, match="between 1 and 5") as raised:
        fetch_mission_frames(mission)
    assert (raised.value.key, raised.value.params) == (
        "invalid_mission",
        {"missions": 5},
    )


def test_fetch_mission_frames_downloads_once(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(text=MISSION_PAGE, raise_for_status=lambda: None)

    monkeypatch.setattr("orbiter.lpi.requests.get", fake_get)

    assert fetch_mission_frames(1) == ["1005", "1006"]
    assert fetch_mission_frames(1) == ["1005", "1006"]
    assert calls == ["https://www.lpi.usra.edu/resources/lunarorbiter/mission/?1"]


def test_parse_frame_page_requires_principal_point():
    with pytest.raises(LpiError, match="No coordinates") as raised:
        parse_frame_page("1041", '<a href="/images/preview/1041_med.jpg">image</a>')
    assert raised.value.key == "no_coordinates"


def test_fetch_frame_rejects_invalid_id_without_network(monkeypatch):
    def fail_if_requested(*args, **kwargs):
        pytest.fail("No debe hacer solicitudes para un ID inválido")

    monkeypatch.setattr("orbiter.lpi.requests.get", fail_if_requested)

    with pytest.raises(LpiError, match="digits only") as raised:
        fetch_frame("10/41")
    assert raised.value.key == "invalid_frame_id"


def test_fetch_frame_downloads_page_and_preview(monkeypatch):
    responses = iter(
        [
            SimpleNamespace(text=FRAME_PAGE, raise_for_status=lambda: None),
            SimpleNamespace(content=b"jpeg-data", raise_for_status=lambda: None),
        ]
    )
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return next(responses)

    monkeypatch.setattr("orbiter.lpi.requests.get", fake_get)
    frame = fetch_frame("1041")

    assert frame.frame_id == "1041"
    assert frame.mission == "Lunar Orbiter 1"
    assert frame.latitude == 3.3
    assert frame.longitude == 39.15
    assert frame.image_bytes == b"jpeg-data"
    assert len(calls) == 2
    assert calls[1][0] == frame.image_url


def test_fetch_frame_reuses_cached_result(monkeypatch):
    frame_page = FRAME_PAGE.replace("1041", "1042")
    responses = iter(
        [
            SimpleNamespace(text=frame_page, raise_for_status=lambda: None),
            SimpleNamespace(content=b"cached-jpeg", raise_for_status=lambda: None),
        ]
    )
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return next(responses)

    monkeypatch.setattr("orbiter.lpi.requests.get", fake_get)
    first_result = fetch_frame("1042")
    second_result = fetch_frame(" 1042 ")

    assert first_result is second_result
    assert len(calls) == 2
