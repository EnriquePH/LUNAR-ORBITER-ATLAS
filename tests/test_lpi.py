from types import SimpleNamespace

import pytest

from orbiter.lpi import fetch_frame, parse_frame_page

FRAME_PAGE = """
<table>
  <tr><td>Mission:</td><td>Lunar Orbiter 1</td></tr>
  <tr><td>Principal Point:</td><td>Latitude:</td><td>3.30°</td>
      <td>Longitude:</td><td>39.15°</td></tr>
</table>
<a href="../images/preview/1041_med.jpg">medium</a>
"""


def test_parse_frame_page_resolves_relative_preview_url():
    metadata = parse_frame_page("1041", FRAME_PAGE)

    assert metadata == {
        "mission": "Lunar Orbiter 1",
        "latitude": 3.3,
        "longitude": 39.15,
        "image_url": "https://www.lpi.usra.edu/resources/lunarorbiter/images/preview/1041_med.jpg",
    }


def test_parse_frame_page_requires_principal_point():
    with pytest.raises(ValueError, match="No se encontraron coordenadas"):
        parse_frame_page("1041", '<a href="/images/preview/1041_med.jpg">image</a>')


def test_fetch_frame_rejects_invalid_id_without_network(monkeypatch):
    def fail_if_requested(*args, **kwargs):
        pytest.fail("No debe hacer solicitudes para un ID inválido")

    monkeypatch.setattr("orbiter.lpi.requests.get", fail_if_requested)

    with pytest.raises(ValueError, match="solo números"):
        fetch_frame("10/41")


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