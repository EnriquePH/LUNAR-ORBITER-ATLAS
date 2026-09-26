"""App settings read from ``config.json`` (or ``$ORBITER_CONFIG``).

Example ``config.json``::

    {"host": "127.0.0.1", "port": 8050, "language": "es"}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields
from pathlib import Path

from orbiter.i18n import LANGUAGES


@dataclass(frozen=True)
class AppConfig:
    """Validated settings; each field defaults to the value shown.

    Attributes:
        host: Interface the server listens on.
        port: TCP port, 1–65535.
        language: Default interface language, ``"es"`` or ``"en"``.
    """

    host: str = "127.0.0.1"
    port: int = 8050
    language: str = "es"

    @property
    def url(self) -> str:
        """Address to open in a browser, e.g. ``http://127.0.0.1:8050/``."""
        return f"http://{self.host}:{self.port}/"


def config_path() -> Path:
    """Return ``$ORBITER_CONFIG`` if set, else ``config.json`` in the cwd."""
    return Path(os.environ.get("ORBITER_CONFIG", Path.cwd() / "config.json"))


def load_config(path: Path | None = None) -> AppConfig:
    """Read and validate the JSON config.

    A missing file, or a key left out of it, falls back to the defaults of
    :class:`AppConfig`. Unknown keys are rejected so that typos are noticed.

    Args:
        path: File to read; defaults to :func:`config_path`.

    Returns:
        The validated settings.

    Raises:
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: For unknown keys, an empty or non-string ``host``, a
            ``port`` that is not an integer from 1 to 65535, or an unsupported
            ``language``.
    """
    path = Path(path) if path is not None else config_path()
    if not path.exists():
        return AppConfig()

    data = json.loads(path.read_text())
    known = {field.name for field in fields(AppConfig)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"Unknown keys in {path}: {', '.join(sorted(unknown))}")

    config = AppConfig(**data)
    if not isinstance(config.host, str) or not config.host:
        raise ValueError(f"'host' in {path} must be a non-empty string")
    # bool is a subclass of int, so `true` would otherwise pass as port 1.
    port_is_int = isinstance(config.port, int) and not isinstance(config.port, bool)
    if not port_is_int or not 1 <= config.port <= 65535:
        raise ValueError(f"'port' in {path} must be an integer from 1 to 65535")
    if config.language not in LANGUAGES:
        raise ValueError(f"'language' in {path} must be one of {LANGUAGES}")
    return config
