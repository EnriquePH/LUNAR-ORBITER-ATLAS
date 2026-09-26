"""Small client for Lunar Orbiter frame pages in the LPI archive."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from orbiter.urls import MISSIONS_NUM, frame_url, mission_url

USER_AGENT = "LunarOrbiterLocalViewer/0.1 (educational; +https://www.energycode.org/)"


class LpiError(ValueError):
    """A problem with LPI data, identified by a translatable ``key``.

    The app turns ``key`` and ``params`` into text with ``orbiter.i18n``; the
    plain message is English for logs and non-UI callers.
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


@dataclass(frozen=True)
class OrbiterFrame:
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
    match = re.search(rf"{re.escape(label)}:\s*{_NUMBER}", section, re.IGNORECASE)
    return float(match.group(1)) if match else None


def parse_frame_page(frame_id: str, page_html: str) -> dict[str, str | float | None]:
    """Extract mission, coordinates, illumination, and preview URL.

    Principal point and preview are required; the other fields become ``None``
    when the page does not list them.
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

    image_url = next(
        (url for url in image_urls if url.endswith("_med.jpg")), image_urls[0]
    )
    image_url = urljoin(frame_url(frame_id), image_url)

    return {
        "mission": mission_match.group(1) if mission_match else "Lunar Orbiter",
        "latitude": float(point_match.group(1)),
        "longitude": float(point_match.group(2)),
        "image_url": image_url,
        **{
            key: _optional_number(_section(text, section), label)
            for key, section, label in _OPTIONAL_FIELDS
        },
    }


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
    """Fetch one frame page and its medium-resolution LPI preview."""
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
    """Fetch the frame IDs of one mission (1–5); results are cached."""
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
