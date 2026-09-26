import pytest

from orbiter.lpi import clear_cache


@pytest.fixture(autouse=True)
def clear_lpi_caches():
    clear_cache()
    yield
    clear_cache()
