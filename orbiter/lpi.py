"""Client and parser for the LPI Lunar Orbiter Photo Gallery.

Units used throughout: latitudes, longitudes and angles in degrees (east and
north positive), altitudes in kilometres.

Network calls use ``requests`` with timeouts and keep results in small
in-memory LRU caches; :func:`clear_cache` empties them. Functions raise
:class:`LpiError` for invalid input or pages without the expected data, and let
``requests.RequestException`` propagate for HTTP and connection failures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TypedDict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from orbiter.urls import MISSIONS_NUM, frame_url, mission_url

USER_AGENT = "LunarOrbiterLocalViewer/1.0 (educational; +https://www.energycode.org/)"


class LpiError(ValueError):
    """A problem with LPI data, identified by a translatable ``key``.

    The app turns ``key`` and ``params`` into text with ``orbiter.i18n``; the
    plain message is English for logs and non-UI callers.

    Args:
        key: One of ``MESSAGES``: ``invalid_frame_id``, ``no_coordinates``,
            ``no_preview``, ``invalid_mission`` or ``no_frames``.
        **params: Values interpolated into the message, e.g. ``frame_id``.
    """

    MESSAGES = {
        "invalid_frame_id": "The frame ID must contain digits only.",
        "no_coordinates": "No coordinates found for frame {frame_id}.",
        "no_preview": "No preview found for frame {frame_id}.",
        "invalid_mission": "The mission must be between 1 and {missions}.",
        "no_frames": "No frames found for mission {mission}.",
    }

    def __init__(self, key: str, **params: object):
        self.key = key
        self.params = params
        super().__init__(self.MESSAGES[key].format(**params))


class FrameMetadata(TypedDict):
    """Fields parsed from a frame page.

    ``mission``, ``latitude``, ``longitude`` and ``image_url`` are always set.
    The spacecraft and illumination fields are ``None`` when the page does not
    list them. Degrees for positions and angles, kilometres for altitude.
    """

    mission: str
    latitude: float
    longitude: float
    image_url: str
    spacecraft_altitude_km: float | None
    spacecraft_latitude: float | None
    spacecraft_longitude: float | None
    sun_azimuth: float | None
    incidence_angle: float | None
    emission_angle: float | None
    phase_angle: float | None


@dataclass(frozen=True)
class OrbiterFrame:
    """A frame's metadata plus the bytes of its LPI preview JPEG.

    ``latitude``/``longitude`` are the principal point (image centre) in
    degrees; the optional fields follow :class:`FrameMetadata`.
    """

    frame_id: str
    mission: str
    latitude: float
    longitude: float
    image_url: str
    image_bytes: bytes
    spacecraft_altitude_km: float | None = None
    spacecraft_latitude: float | None = None
    spacecraft_longitude: float | None = None
    sun_azimuth: float | None = None
    incidence_angle: float | None = None
    emission_angle: float | None = None
    phase_angle: float | None = None


_NUMBER = r"(-?\d+(?:\.\d+)?)"
# Optional fields: (key, section label, value label). Each value is the first
# number after its label inside its section of the page text.
_OPTIONAL_FIELDS = (
    ("spacecraft_altitude_km", "Spacecraft Position", "Altitude"),
    ("spacecraft_latitude", "Spacecraft Position", "Latitude"),
    ("spacecraft_longitude", "Spacecraft Position", "Longitude"),
    ("sun_azimuth", "Illumination", "Sun Azimuth"),
    ("incidence_angle", "Illumination", "Incident Angle"),
    ("emission_angle", "Illumination", "Emission Angle"),
    ("phase_angle", "Illumination", "Phase Angle"),
)
_SECTION_LABELS = (
    "Spacecraft Position",
    "Principal Point",
    "Illumination",
    "Hi Resolution Plate",
)


def _section(text: str, label: str) -> str:
    """Return the page text between ``label:`` and the next known section."""
    start = re.search(rf"{label}:", text, re.IGNORECASE)
    if start is None:
        return ""
    others = "|".join(re.escape(other) for other in _SECTION_LABELS if other != label)
    end = re.search(rf"(?:{others})", text[start.end() :], re.IGNORECASE)
    return text[start.end() : start.end() + end.start()] if end else text[start.end() :]


def _optional_number(section: str, label: str) -> float | None:
    """Return the first number after ``label:`` in ``section``, if any."""
    match = re.search(rf"{re.escape(label)}:\s*{_NUMBER}", section, re.IGNORECASE)
    return float(match.group(1)) if match else None


def parse_frame_page(frame_id: str, page_html: str) -> FrameMetadata:
    """Extract mission, coordinates, illumination and preview URL from a page.

    The preview prefers the medium-resolution JPEG (``_med``), then the middle
    high-resolution sub-frame (``_h2``), then any other plate; its URL is made
    absolute. That order matches the image the gallery thumbnail shows.

    Args:
        frame_id: Frame identifier the page belongs to, e.g. ``"1041"``.
        page_html: HTML of the frame page.

    Returns:
        The parsed fields; see :class:`FrameMetadata` for keys and units.

    Raises:
        LpiError: ``no_coordinates`` if the principal point is missing, or
            ``no_preview`` if no preview link for ``frame_id`` is found.
    """
    soup = BeautifulSoup(page_html, "html.parser")
    text = " ".join(soup.stripped_strings)

    mission_match = re.search(r"Mission:\s*(Lunar Orbiter\s+\d+)", text, re.IGNORECASE)
    point_match = re.search(
        r"Principal Point:\s*Latitude:\s*(-?\d+(?:\.\d+)?)°?\s*"
        r"Longitude:\s*(-?\d+(?:\.\d+)?)°?",
        text,
        re.IGNORECASE,
    )
    if point_match is None:
        raise LpiError("no_coordinates", frame_id=frame_id)

    image_pattern = re.compile(
        rf"/images/preview/{re.escape(frame_id)}_(?:med|h[123])\.jpg$",
        re.IGNORECASE,
    )
    image_urls = [
        link.get("href", "") for link in soup.find_all("a", href=image_pattern)
    ]
    if not image_urls:
        raise LpiError("no_preview", frame_id=frame_id)

    # Prefer the image the LPI thumbnail shows: the medium-resolution frame, or
    # else the middle high-resolution sub-frame (h2), centred like the frame.
    image_url = next(
        (
            url
            for suffix in ("_med.jpg", "_h2.jpg")
            for url in image_urls
            if url.lower().endswith(suffix)
        ),
        image_urls[0],
    )
    image_url = urljoin(frame_url(frame_id), image_url)

    optional = {
        key: _optional_number(_section(text, section), label)
        for key, section, label in _OPTIONAL_FIELDS
    }
    return FrameMetadata(
        mission=mission_match.group(1) if mission_match else "Lunar Orbiter",
        latitude=float(point_match.group(1)),
        longitude=float(point_match.group(2)),
        image_url=image_url,
        **optional,
    )


def parse_mission_page(page_html: str) -> list[str]:
    """Return the frame IDs linked from a mission gallery, in page order."""
    soup = BeautifulSoup(page_html, "html.parser")
    frame_ids = []
    for link in soup.find_all("a", href=re.compile(r"frame/\?\d+$")):
        frame_id = link["href"].rsplit("?", 1)[1]
        if frame_id not in frame_ids:
            frame_ids.append(frame_id)
    return frame_ids


def fetch_frame(frame_id: str) -> OrbiterFrame:
    """Download a frame's page and preview image (two HTTP requests).

    The last 16 frames are kept in memory, so repeated calls are free until
    :func:`clear_cache` is called. Surrounding whitespace in the ID is ignored.

    Args:
        frame_id: Numeric frame identifier, e.g. ``"1041"``.

    Returns:
        The frame's metadata and preview bytes.

    Raises:
        LpiError: ``invalid_frame_id`` for non-numeric IDs (checked before any
            request), or a parsing error from :func:`parse_frame_page`.
        requests.RequestException: On HTTP errors, timeouts or no connection.
    """
    frame_id = str(frame_id).strip()
    if not frame_id.isdigit():
        raise LpiError("invalid_frame_id")

    return _fetch_frame_cached(frame_id)


@lru_cache(maxsize=16)
def _fetch_frame_cached(frame_id: str) -> OrbiterFrame:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(frame_url(frame_id), headers=headers, timeout=20)
    response.raise_for_status()
    metadata = parse_frame_page(frame_id, response.text)

    image_response = requests.get(
        str(metadata["image_url"]), headers=headers, timeout=30
    )
    image_response.raise_for_status()

    return OrbiterFrame(
        frame_id=frame_id,
        mission=str(metadata["mission"]),
        latitude=float(metadata["latitude"]),
        longitude=float(metadata["longitude"]),
        image_url=str(metadata["image_url"]),
        image_bytes=image_response.content,
        **{key: metadata[key] for key, _, _ in _OPTIONAL_FIELDS},
    )


def fetch_mission_frames(mission: int) -> list[str]:
    """Download the list of frame IDs of a mission (one HTTP request).

    Each mission's list is cached in memory until :func:`clear_cache`.

    Args:
        mission: Mission number from 1 to ``MISSIONS_NUM``.

    Returns:
        Frame IDs in gallery order, without duplicates.

    Raises:
        LpiError: ``invalid_mission`` for numbers outside 1–5 (checked before
            any request), or ``no_frames`` if the page lists none.
        requests.RequestException: On HTTP errors, timeouts or no connection.
    """
    if mission not in range(1, MISSIONS_NUM + 1):
        raise LpiError("invalid_mission", missions=MISSIONS_NUM)
    return list(_fetch_mission_frames_cached(mission))


@lru_cache(maxsize=MISSIONS_NUM)
def _fetch_mission_frames_cached(mission: int) -> tuple[str, ...]:
    response = requests.get(
        mission_url(mission), headers={"User-Agent": USER_AGENT}, timeout=20
    )
    response.raise_for_status()
    frame_ids = parse_mission_page(response.text)
    if not frame_ids:
        raise LpiError("no_frames", mission=mission)
    return tuple(frame_ids)


def clear_cache() -> None:
    """Forget the frames and mission lists kept in memory."""
    _fetch_frame_cached.cache_clear()
    _fetch_mission_frames_cached.cache_clear()
