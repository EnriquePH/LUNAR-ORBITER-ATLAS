"""URLs of the LPI Lunar Orbiter Photo Gallery.

These helpers only build URLs; they do not validate identifiers or check that
the page exists. Validation happens in :mod:`orbiter.lpi`.
"""

MISSIONS_NUM = 5
ORBITER_URL = "https://www.lpi.usra.edu/resources/lunarorbiter"


def mission_url(num: int | str) -> str:
    """Return the gallery page listing a mission's frames.

    Args:
        num: Mission number, normally 1 to ``MISSIONS_NUM``. Not validated.

    Returns:
        A URL such as ``.../lunarorbiter/mission/?1``.
    """
    return f"{ORBITER_URL}/mission/?{num}"


def frame_url(num: int | str) -> str:
    """Return the LPI page of a single frame.

    Args:
        num: Frame identifier such as ``"1041"``. Not validated.

    Returns:
        A URL such as ``.../lunarorbiter/frame/?1041``.
    """
    return f"{ORBITER_URL}/frame/?{num}"
