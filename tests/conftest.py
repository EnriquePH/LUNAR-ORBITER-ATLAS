import pytest

from orbiter.lpi import _fetch_frame_cached, _fetch_mission_frames_cached


@pytest.fixture(autouse=True)
def clear_lpi_caches():
    _fetch_frame_cached.cache_clear()
    _fetch_mission_frames_cached.cache_clear()
    yield
    _fetch_frame_cached.cache_clear()
    _fetch_mission_frames_cached.cache_clear()
