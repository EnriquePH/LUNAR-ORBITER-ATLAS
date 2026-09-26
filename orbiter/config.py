"""App settings read from ``config.json`` (or ``$ORBITER_CONFIG``)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields
from pathlib import Path

from orbiter.i18n import LANGUAGES


@dataclass(frozen=True)
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8050
    language: str = "es"

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"


def config_path() -> Path:
    return Path(os.environ.get("ORBITER_CONFIG", Path.cwd() / "config.json"))


def load_config(path: Path | None = None) -> AppConfig:
    """Read the JSON config; missing file or keys fall back to the defaults."""
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
    if not isinstance(config.port, int) or not 1 <= config.port <= 65535:
        raise ValueError(f"'port' in {path} must be an integer from 1 to 65535")
    if config.language not in LANGUAGES:
        raise ValueError(f"'language' in {path} must be one of {LANGUAGES}")
    return config
