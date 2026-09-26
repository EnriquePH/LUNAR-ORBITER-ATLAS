import pytest

from orbiter.lpi import _fetch_frame_cached


@pytest.fixture(autouse=True)
def clear_frame_cache():
    _fetch_frame_cached.cache_clear()
    yield
    _fetch_frame_cached.cache_clear()
