"""Small client for Lunar Orbiter frame pages in the LPI archive."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from orbiter.urls import frame_url

USER_AGENT = "LunarOrbiterLocalViewer/0.1 (educational; contact: local user)"


@dataclass(frozen=True)
class OrbiterFrame:
    frame_id: str
    mission: str
    latitude: float
    longitude: float
    image_url: str
    image_bytes: bytes


def parse_frame_page(frame_id: str, page_html: str) -> dict[str, str | float]:
    """Extract mission, principal-point coordinates, and preview URL."""
    soup = BeautifulSoup(page_html, "html.parser")
    text = " ".join(soup.stripped_strings)

    mission_match = re.search(
        r"Mission:\s*(Lunar Orbiter\s+\d+)", text, re.IGNORECASE
    )
    point_match = re.search(
        r"Principal Point:\s*Latitude:\s*(-?\d+(?:\.\d+)?)°?\s*"
        r"Longitude:\s*(-?\d+(?:\.\d+)?)°?",
        text,
        re.IGNORECASE,
    )
    if point_match is None:
        raise ValueError(f"No se encontraron coordenadas para el fotograma {frame_id}.")

    image_pattern = re.compile(
        rf"/images/preview/{re.escape(frame_id)}_(?:med|h[123])\.jpg$",
        re.IGNORECASE,
    )
    image_urls = [
        link.get("href", "")
        for link in soup.find_all("a", href=image_pattern)
    ]
    if not image_urls:
        raise ValueError(f"No se encontró una vista previa para el fotograma {frame_id}.")

    image_url = next((url for url in image_urls if url.endswith("_med.jpg")), image_urls[0])
    image_url = urljoin(frame_url(frame_id), image_url)

    return {
        "mission": mission_match.group(1) if mission_match else "Lunar Orbiter",
        "latitude": float(point_match.group(1)),
        "longitude": float(point_match.group(2)),
        "image_url": image_url,
    }


def fetch_frame(frame_id: str) -> OrbiterFrame:
    """Fetch one frame page and its medium-resolution LPI preview."""
    frame_id = str(frame_id).strip()
    if not frame_id.isdigit():
        raise ValueError("El identificador del fotograma debe contener solo números.")

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
    )