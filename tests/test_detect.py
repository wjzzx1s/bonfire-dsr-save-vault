from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bonfire import detect
from bonfire.paths import SAVE_FILENAME


def _make_save(path: Path, payload: bytes = b"BND4" + b"x" * 4096) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


class DetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home)}, clear=False)
        self.env.start()
        for key in ("WINEPREFIX", "STEAM_ROOT"):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        self.env.stop()
        self.tmp.cleanup()

    def test_finds_proton_save_from_steam_library_file(self) -> None:
        library = Path(self.tmp.name) / "SteamLibrary"
        steam = self.home / ".local" / "share" / "Steam"
        (steam / "steamapps").mkdir(parents=True)
        (steam / "steamapps" / "libraryfolders.vdf").write_text(
            '"libraryfolders"\n{\n "0"\n {\n  "path" "' + str(library) + '"\n }\n}\n'
        )
        save = _make_save(
            library / "steamapps" / "compatdata" / "570940" / "pfx" / "drive_c"
            / "users" / "steamuser" / "Documents" / "NBGI" / "DARK SOULS REMASTERED"
            / "76561197960287930" / SAVE_FILENAME
        )

        result = detect.detect()

        self.assertTrue(result.found)
        self.assertEqual(result.save_file, save)
        self.assertIn("Proton", result.source)
        self.assertTrue(any("Steam library" in note for note in result.notes))

    def test_prefers_most_recent_of_two_libraries(self) -> None:
        steam = self.home / ".local" / "share" / "Steam"
        (steam / "steamapps").mkdir(parents=True)
        second = Path(self.tmp.name) / "Lib2"
        (steam / "steamapps" / "libraryfolders.vdf").write_text(
            '"libraryfolders"\n{\n "1"\n {\n  "path" "' + str(second) + '"\n }\n}\n'
        )
        older = _make_save(
            steam / "steamapps" / "compatdata" / "570940" / "pfx" / "drive_c" / "users"
            / "steamuser" / "Documents" / "NBGI" / "DARK SOULS REMASTERED" / "11111111111111111"
            / SAVE_FILENAME
        )
        newer = _make_save(
            second / "steamapps" / "compatdata" / "570940" / "pfx" / "drive_c" / "users"
            / "steamuser" / "Documents" / "NBGI" / "DARK SOULS REMASTERED" / "22222222222222222"
            / SAVE_FILENAME
        )
        os.utime(older, (1_600_000_000, 1_600_000_000))
        os.utime(newer, (1_700_000_000, 1_700_000_000))

        result = detect.detect()

        self.assertEqual(result.save_file, newer)

    def test_scans_wine_prefix(self) -> None:
        prefix = Path(self.tmp.name) / "wineprefix"
        save = _make_save(
            prefix / "drive_c" / "users" / "weiqi" / "Documents" / "NBGI"
            / "DARK SOULS REMASTERED" / "76561190000000000" / SAVE_FILENAME
        )
        with mock.patch.dict(os.environ, {"WINEPREFIX": str(prefix)}):
            result = detect.detect()

        self.assertEqual(result.save_file, save)
        self.assertIn("Wine", result.source)

    def test_reports_when_nothing_exists(self) -> None:
        result = detect.detect()

        self.assertFalse(result.found)
        self.assertIsNone(result.save_file)
        self.assertTrue(result.notes)


if __name__ == "__main__":
    unittest.main()
