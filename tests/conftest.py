"""Shared pytest fixtures: keep the LPI caches empty between tests."""

import pytest

from orbiter.lpi import clear_cache


@pytest.fixture(autouse=True)
def clear_lpi_caches():
    """Empty the LPI caches before and after each test."""
    clear_cache()
    yield
    clear_cache()
