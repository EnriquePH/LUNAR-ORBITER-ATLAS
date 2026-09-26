import json
import threading
from io import BytesIO
from types import SimpleNamespace

import pytest
import requests
from PIL import Image

from orbiter.catalog import (
    TILE_SIZE,
    MissionLoader,
    TileStore,
    download,
    main,
    thumbnail_url,
)

FRAME_PAGE = """
Mission: Lunar Orbiter 1 Spacecraft Position: Altitude: 256.43 km
Latitude: 4.29° Longitude: 41.17° Principal Point: Latitude: 3.30°
Longitude: 39.15° <a href="../images/preview/{id}_med.jpg">Preview</a>
"""


def _jpeg(size=(120, 141)) -> bytes:
    buffer = BytesIO()
    Image.new("L", size, color=90).save(buffer, format="JPEG")
    return buffer.getvalue()


class FakeSession:
    def __init__(self, fail_ids=()):
        self.headers = {}
        self.urls = []
        self.fail_ids = set(fail_ids)

    def get(self, url, timeout):
        self.urls.append(url)
        frame_id = url.rsplit("?", 1)[-1].rsplit("/", 1)[-1].removesuffix(".jpg")
        if frame_id in self.fail_ids:
            raise requests.ConnectionError("sin red")
        if "/frame/" in url:
            text = FRAME_PAGE.replace("{id}", frame_id)
            return SimpleNamespace(text=text, raise_for_status=lambda: None)
        return SimpleNamespace(content=_jpeg(), raise_for_status=lambda: None)


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def store(tmp_path, session):
    return TileStore(tmp_path, delay=0, session_factory=lambda: session)


def test_tile_store_downloads_once_then_reads_disk(store, session, tmp_path):
    tile = store.load("1041")
    offline = FakeSession(fail_ids={"1041"})
    again = TileStore(tmp_path, delay=0, session_factory=lambda: offline)

    cached = again.load("1041")

    assert (tile.latitude, tile.longitude, tile.altitude_km) == (3.3, 39.15, 256.43)
    assert (tile.spacecraft_latitude, tile.spacecraft_longitude) == (4.29, 41.17)
    assert max(tile.texture.shape) <= max(TILE_SIZE)
    assert session.urls[-1] == thumbnail_url("1041")
    assert offline.urls == []
    assert not list(tmp_path.rglob("*.tmp"))
    assert cached.latitude == 3.3
    saved = json.loads((tmp_path / "frames" / "1041.json").read_text())
    assert saved["spacecraft_altitude_km"] == 256.43


def _wait_until_finished(loader, mission):
    for _ in range(200):
        if loader.progress(mission).finished:
            return loader.progress(mission)
        threading.Event().wait(0.01)
    pytest.fail("el loader no terminó")


def test_tile_store_spaces_request_starts(tmp_path, session, monkeypatch):
    starts = []
    monkeypatch.setattr("orbiter.catalog.time.sleep", lambda seconds: None)
    monkeypatch.setattr("orbiter.catalog.time.monotonic", lambda: 100.0)
    store = TileStore(tmp_path, delay=0.25, session_factory=lambda: session)
    original_get = session.get

    def recording_get(url, timeout):
        starts.append(store._next_request)
        return original_get(url, timeout)

    session.get = recording_get
    store.load("1041")

    assert starts == [100.25, 100.5]


def test_mission_loader_collects_tiles_and_counts_failures(store, session, monkeypatch):
    session.fail_ids = {"1006"}
    monkeypatch.setattr(
        "orbiter.catalog.fetch_mission_frames", lambda m: ["1005", "1006", "1007"]
    )
    loader = MissionLoader(store)

    loader.start(1)
    loader.start(1)
    progress = _wait_until_finished(loader, 1)

    assert sorted(progress.tiles) == ["1005", "1007"]
    assert (progress.total, progress.failed, progress.error) == (3, 1, None)


def test_mission_loader_reports_listing_error_and_allows_retry(store, monkeypatch):
    def fail(mission):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr("orbiter.catalog.fetch_mission_frames", fail)
    loader = MissionLoader(store)
    loader.start(2)
    assert str(_wait_until_finished(loader, 2).error) == "sin red"

    monkeypatch.setattr("orbiter.catalog.fetch_mission_frames", lambda m: ["2001"])
    loader.start(2)
    assert sorted(_wait_until_finished(loader, 2).tiles) == ["2001"]


def test_download_fills_the_cache_and_reports_failures(
    tmp_path, session, monkeypatch, capsys
):
    session.fail_ids = {"1006"}
    monkeypatch.setattr(
        "orbiter.catalog.fetch_mission_frames", lambda m: ["1005", "1006"]
    )
    monkeypatch.setattr(
        "orbiter.catalog.TileStore",
        lambda cache_dir: TileStore(tmp_path, delay=0, session_factory=lambda: session),
    )

    assert download([1], poll_seconds=0.01) == 1
    assert (tmp_path / "frames" / "1005.json").exists()
    assert "Mission 1: 1/2 frames, 1 failed" in capsys.readouterr().out


def test_main_downloads_all_missions_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr("orbiter.catalog.download", lambda m: calls.append(m) or 0)

    assert main([]) == 0
    assert main(["2", "4"]) == 0
    assert calls == [[1, 2, 3, 4, 5], [2, 4]]
