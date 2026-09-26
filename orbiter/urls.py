MISSIONS_NUM = 5
ORBITER_URL = "https://www.lpi.usra.edu/resources/lunarorbiter"


def mission_url(num: int | str) -> str:
    return f"{ORBITER_URL}/mission/?{num}"


def frame_url(num: int | str) -> str:
    return f"{ORBITER_URL}/frame/?{num}"
