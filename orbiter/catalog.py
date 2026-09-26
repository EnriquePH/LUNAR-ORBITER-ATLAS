"""Background loading of every frame in a mission, with an on-disk cache.

Each frame needs its LPI page (for coordinates) and its small thumbnail. Both
are cached under ``data/lpi`` (or ``$ORBITER_CACHE_DIR``) so a mission is only
downloaded once. ``DOWNLOAD_WORKERS`` threads share one rate limit, so request
starts are always at least ``REQUEST_DELAY_SECONDS`` apart.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from orbiter.globe import GlobeImage
from orbiter.lpi import USER_AGENT, fetch_mission_frames, parse_frame_page
from orbiter.urls import ORBITER_URL, frame_url

REQUEST_DELAY_SECONDS = 0.25
DOWNLOAD_WORKERS = 3
TILE_SIZE = (20, 20)


def default_cache_dir() -> Path:
    return Path(os.environ.get("ORBITER_CACHE_DIR", Path.cwd() / "data" / "lpi"))


def thumbnail_url(frame_id: str) -> str:
    return f"{ORBITER_URL}/images/thumb/{frame_id}.jpg"


def _texture(image_bytes: bytes) -> np.ndarray:
    image = Image.open(BytesIO(image_bytes)).convert("L")
    image.thumbnail(TILE_SIZE, Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.uint8)


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def _write_atomic(path: Path, data: bytes) -> None:
    """Write via a temporary file so an interrupted run never leaves a partial one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


class TileStore:
    """Read frame tiles from disk, downloading the missing ones.

    Safe to call from several threads: each thread gets its own HTTP session.
    """

    def __init__(
        self,
        cache_dir: Path,
        delay: float = REQUEST_DELAY_SECONDS,
        session_factory: Callable[[], requests.Session] = _new_session,
    ):
        self.cache_dir = Path(cache_dir)
        self.delay = delay
        self._session_factory = session_factory
        self._local = threading.local()
        self._rate_lock = threading.Lock()
        self._next_request = 0.0

    def _get(self, url: str) -> requests.Response:
        with self._rate_lock:
            start = max(time.monotonic(), self._next_request)
            self._next_request = start + self.delay
        time.sleep(max(0.0, start - time.monotonic()))

        if not hasattr(self._local, "session"):
            self._local.session = self._session_factory()
        response = self._local.session.get(url, timeout=20)
        response.raise_for_status()
        return response

    def load(self, frame_id: str) -> GlobeImage:
        metadata_path = self.cache_dir / "frames" / f"{frame_id}.json"
        thumbnail_path = self.cache_dir / "thumbs" / f"{frame_id}.jpg"

        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
        else:
            page = self._get(frame_url(frame_id)).text
            metadata = parse_frame_page(frame_id, page)
            _write_atomic(metadata_path, json.dumps(metadata).encode())

        if thumbnail_path.exists():
            image_bytes = thumbnail_path.read_bytes()
        else:
            image_bytes = self._get(thumbnail_url(frame_id)).content
            _write_atomic(thumbnail_path, image_bytes)

        return GlobeImage(
            frame_id=frame_id,
            latitude=float(metadata["latitude"]),
            longitude=float(metadata["longitude"]),
            altitude_km=metadata.get("spacecraft_altitude_km"),
            texture=_texture(image_bytes),
        )


@dataclass
class MissionProgress:
    total: int = 0
    failed: int = 0
    finished: bool = False
    error: str | None = None
    tiles: dict[str, GlobeImage] = field(default_factory=dict)


class MissionLoader:
    """Load whole missions in background threads; safe to poll from callbacks."""

    def __init__(self, store: TileStore):
        self.store = store
        self._lock = threading.Lock()
        self._missions: dict[int, MissionProgress] = {}

    def start(self, mission: int) -> None:
        """Begin loading a mission unless it is already loading or loaded."""
        with self._lock:
            current = self._missions.get(mission)
            # A failed mission listing may be retried; anything else runs once.
            if current is not None and current.error is None:
                return
            self._missions[mission] = MissionProgress()
        threading.Thread(target=self._run, args=(mission,), daemon=True).start()

    def progress(self, mission: int) -> MissionProgress:
        """Return a snapshot that the loader thread will not mutate."""
        with self._lock:
            current = self._missions.get(mission, MissionProgress())
            return MissionProgress(
                total=current.total,
                failed=current.failed,
                finished=current.finished,
                error=current.error,
                tiles=dict(current.tiles),
            )

    def _run(self, mission: int) -> None:
        progress = self._missions[mission]
        try:
            frame_ids = fetch_mission_frames(mission)
        except (requests.RequestException, ValueError) as error:
            with self._lock:
                progress.error = str(error)
                progress.finished = True
            return

        with self._lock:
            progress.total = len(frame_ids)

        def load(frame_id: str) -> None:
            try:
                tile = self.store.load(frame_id)
            except (requests.RequestException, ValueError, OSError):
                with self._lock:
                    progress.failed += 1
                return
            with self._lock:
                progress.tiles[frame_id] = tile

        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
            list(executor.map(load, frame_ids))
        with self._lock:
            progress.finished = True
