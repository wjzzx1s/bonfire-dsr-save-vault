"""Filesystem locations and app constants."""
from __future__ import annotations

import os
from pathlib import Path

APP_ID = "bonfire"
APP_NAME = "Bonfire"
APP_TAGLINE = "Dark Souls: Remastered — Save Vault"
VERSION = "1.0.0"

SAVE_FILENAME = "DRAKS0005.sl2"
STEAM_APP_ID = "570940"


def _xdg(env_var: str, fallback: str) -> Path:
    value = os.environ.get(env_var)
    if value:
        return Path(value).expanduser()
    return Path.home() / fallback


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP_ID


def config_file() -> Path:
    return config_dir() / "config.json"


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / APP_ID


def backups_dir() -> Path:
    return data_dir() / "backups"


def log_file() -> Path:
    return data_dir() / "bonfire.log"


def ensure_dirs() -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    backups_dir().mkdir(parents=True, exist_ok=True)


def asset_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent.parent.joinpath("assets", *parts)
