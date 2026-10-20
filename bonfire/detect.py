"""Locate the Dark Souls: Remastered save using information from this system.

The game is a Windows title; on Linux it normally runs through Steam Proton,
so the save lives inside the Proton prefix for Steam app 570940.  Native
Windows, plain Wine and Bottles prefixes are handled too.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .paths import SAVE_FILENAME, STEAM_APP_ID

NATIVE_DOCS_SCORE = 40
WINE_SCORE = 70
PROTON_SCORE = 100

_STEAMID_RE = re.compile(r"^\d{17}$")


@dataclass(frozen=True)
class Candidate:
    save_file: Path
    source: str
    score: int

    @property
    def mtime(self) -> float:
        try:
            return self.save_file.stat().st_mtime
        except OSError:
            return 0.0


@dataclass
class Detection:
    save_file: Path | None = None
    source: str = ""
    candidates: list[Candidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.save_file is not None


def _dedupe(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key not in seen and p.is_dir():
            seen.add(key)
            out.append(p)
    return out


def steam_roots() -> list[Path]:
    """Steam install roots, including Flatpak and the Windows registry entry."""
    roots: list[Path] = []
    env_root = os.environ.get("STEAM_ROOT")
    if env_root:
        roots.append(Path(env_root).expanduser())

    if sys.platform == "win32":
        try:
            import winreg  # type: ignore[import-not-found]

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            roots.append(Path(steam_path))
        except (OSError, ImportError):
            pass
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
            if base:
                roots.append(Path(base) / "Steam")
    else:
        home = Path.home()
        roots += [
            home / ".steam" / "steam",
            home / ".steam" / "root",
            home / ".local" / "share" / "Steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
            home / "Library" / "Application Support" / "Steam",
        ]
    return _dedupe(roots)


def _parse_library_paths(vdf_text: str) -> list[Path]:
    # libraryfolders.vdf is simple enough that a targeted regex is reliable.
    raw = re.findall(r'"path"\s*"((?:[^"\\]|\\.)+)"', vdf_text)
    # VDF escapes backslashes in Windows paths (D:\\Games\\Steam).
    return [Path(p.replace("\\\\", "\\")) for p in raw]


def steam_libraries(notes: list[str] | None = None) -> list[Path]:
    libraries: list[Path] = []
    noted: set[str] = set()
    for root in steam_roots():
        libraries.append(root)
        # root/steamapps/libraryfolders.vdf is the canonical location; some
        # installs keep the file directly under root.
        for vdf in (root / "steamapps" / "libraryfolders.vdf", root / "libraryfolders.vdf"):
            try:
                text = vdf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lib in _parse_library_paths(text):
                libraries.append(lib)
                if notes is not None and str(lib) not in noted:
                    notes.append(f"Steam library: {lib}")
                    noted.add(str(lib))
    return _dedupe(libraries)


def _documents_dirs() -> list[Path]:
    """Documents folders that may contain a Windows-style save tree."""
    dirs: list[Path] = []
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5; handles OneDrive-redirected Documents.
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                dirs.append(Path(buf.value))
        except (OSError, AttributeError):
            pass
        for env in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            base = os.environ.get(env)
            if base:
                dirs.append(Path(base) / "Documents")
    else:
        dirs.append(Path.home() / "Documents")
    return _dedupe(dirs)


def _wine_prefixes() -> list[Path]:
    prefixes: list[Path] = []
    env_prefix = os.environ.get("WINEPREFIX")
    if env_prefix:
        prefixes.append(Path(env_prefix).expanduser())
    prefixes.append(Path.home() / ".wine")

    for pattern in (
        Path.home() / ".local" / "share" / "bottles" / "bottles" / "*",
        Path.home() / ".var" / "app" / "com.usebottles.bottles" / "data" / "bottles" / "bottles" / "*",
    ):
        try:
            prefixes.extend(p for p in pattern.parent.glob(pattern.name) if (p / "drive_c").is_dir())
        except OSError:
            pass

    return _dedupe([p for p in prefixes if (p / "drive_c").is_dir()])


def _add_candidate(
    found: dict[str, Candidate], save_file: Path, source: str, score: int
) -> None:
    try:
        key = str(save_file.resolve())
    except OSError:
        key = str(save_file)
    previous = found.get(key)
    if previous is None or score > previous.score:
        found[key] = Candidate(save_file=save_file, source=source, score=score)


def _prefix_candidates(prefix: Path, source: str, score: int) -> list[Candidate]:
    """Find DRAKS0005.sl2 inside a Wine/Proton prefix's user Documents."""
    out: list[Candidate] = []
    users = prefix / "drive_c" / "users"
    try:
        user_dirs = [p for p in users.iterdir() if p.is_dir()]
    except OSError:
        return out

    for user in user_dirs:
        base = user / "Documents" / "NBGI" / "DARK SOULS REMASTERED"
        try:
            id_dirs = [p for p in base.iterdir() if p.is_dir()]
        except OSError:
            continue
        for id_dir in id_dirs:
            save = id_dir / SAVE_FILENAME
            if save.is_file():
                out.append(Candidate(save, source, score + (5 if _STEAMID_RE.match(id_dir.name) else 0)))
    return out


def detect() -> Detection:
    """Return the most plausible save file, or an explanatory empty result."""
    notes: list[str] = []
    found: dict[str, Candidate] = {}

    libraries = steam_libraries(notes)
    for library in libraries:
        compat = library / "steamapps" / "compatdata" / STEAM_APP_ID
        if not compat.is_dir():
            continue
        prefix = compat / "pfx"
        notes.append(f"Proton prefix for app {STEAM_APP_ID}: {prefix}")
        for cand in _prefix_candidates(prefix, f"Steam · Proton {STEAM_APP_ID}", PROTON_SCORE):
            _add_candidate(found, cand.save_file, cand.source, cand.score)

    for prefix in _wine_prefixes():
        for cand in _prefix_candidates(prefix, f"Wine prefix · {prefix}", WINE_SCORE):
            _add_candidate(found, cand.save_file, cand.source, cand.score)

    for docs in _documents_dirs():
        base = docs / "NBGI" / "DARK SOULS REMASTERED"
        try:
            id_dirs = [p for p in base.iterdir() if p.is_dir()]
        except OSError:
            continue
        for id_dir in id_dirs:
            save = id_dir / SAVE_FILENAME
            if save.is_file():
                _add_candidate(
                    found, save, f"Documents folder · {docs}",
                    NATIVE_DOCS_SCORE + (5 if _STEAMID_RE.match(id_dir.name) else 0),
                )

    candidates = sorted(found.values(), key=lambda c: (c.score, c.mtime), reverse=True)
    if not candidates:
        notes.append("No DRAKS0005.sl2 was found in any known Steam, Proton or Wine location.")
        notes.append("Launch the game once and save, or choose the file manually.")
        return Detection(None, "", [], notes)

    best = candidates[0]
    return Detection(best.save_file, best.source, candidates, notes)
