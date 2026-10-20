"""Persistent user settings, stored as small atomic JSON files."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import paths

DEFAULT_INTERVAL_MIN = 30
DEFAULT_MAX_BACKUPS = 20


@dataclass
class Settings:
    save_file: str | None = None          # explicit override; None = auto-detect
    interval_min: int = DEFAULT_INTERVAL_MIN
    max_backups: int = DEFAULT_MAX_BACKUPS
    auto_enabled: bool = True
    only_when_changed: bool = True

    def normalized(self) -> Settings:
        self.interval_min = max(1, min(int(self.interval_min), 24 * 60))
        self.max_backups = max(1, min(int(self.max_backups), 500))
        self.auto_enabled = bool(self.auto_enabled)
        self.only_when_changed = bool(self.only_when_changed)
        if self.save_file is not None:
            self.save_file = str(self.save_file).strip() or None
        return self


def load(path: Path | None = None) -> Settings:
    path = path or paths.config_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError):
        return Settings()

    known = {f.name for f in fields(Settings)}
    data = {k: v for k, v in raw.items() if k in known}
    try:
        return Settings(**data).normalized()
    except (TypeError, ValueError):
        return Settings()


def save(settings: Settings, path: Path | None = None) -> None:
    path = path or paths.config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(settings.normalized()), indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".config-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
