"""Small OS helpers: game-process detection, file validation, UI plumbing."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .paths import SAVE_FILENAME

GAME_PROCESS_NAMES = ("darksoulsremastered.exe", "darksoulsremastered")


def human_size(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}".replace(".00", "")
        value /= 1024
    return f"{value:.1f} GB"


def game_running() -> bool:
    """Best-effort check for the game process (Proton reports the .exe)."""
    try:
        if sys.platform.startswith("linux"):
            for entry in os.scandir("/proc"):
                if not entry.name.isdigit():
                    continue
                try:
                    with open(f"/proc/{entry.name}/cmdline", "rb") as fh:
                        cmdline = fh.read().decode("utf-8", "replace").lower()
                except OSError:
                    continue
                if any(name in cmdline for name in GAME_PROCESS_NAMES):
                    return True
            return False

        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq DarkSoulsRemastered.exe", "/NH"],
                capture_output=True, text=True, timeout=5, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.lower()
            return "darksoulsremastered" in out

        out = subprocess.run(
            ["pgrep", "-fi", "darksoulsremastered"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return out.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def save_looks_valid(path: Path) -> tuple[bool, str]:
    """Check name, existence and the BND4 container magic used by DS:R."""
    if path.name != SAVE_FILENAME:
        return False, f"Expected a file named {SAVE_FILENAME}."
    if not path.is_file():
        return False, "The save file does not exist (the game creates it on first save)."
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            magic = fh.read(4)
    except OSError as exc:
        return False, f"Cannot read the save file: {exc}"
    if size < 1024:
        return False, f"The file looks too small to be a save ({human_size(size)})."
    if magic != b"BND4":
        return False, "The file does not start with the expected BND4 header."
    return True, ""


def reveal_in_file_manager(path: Path) -> None:
    """Open the containing folder, selecting the file where supported."""
    path = Path(path)
    try:
        if sys.platform.startswith("linux"):
            if path.is_dir():
                subprocess.Popen(["xdg-open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        elif sys.platform == "win32":
            if path.is_dir():
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["open", "-R" if path.is_file() else str(path)])
    except OSError:
        pass
