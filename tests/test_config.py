from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bonfire import config


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            settings = config.Settings(
                save_file="/tmp/DRAKS0005.sl2",
                interval_min=15,
                max_backups=8,
                auto_enabled=False,
                only_when_changed=False,
            )

            config.save(settings, path)
            loaded = config.load(path)

            self.assertEqual(loaded, settings)

    def test_values_are_clamped(self) -> None:
        settings = config.Settings(interval_min=0, max_backups=99999).normalized()
        self.assertEqual(settings.interval_min, 1)
        self.assertEqual(settings.max_backups, 500)

    def test_corrupt_file_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{not json")

            loaded = config.load(path)

            self.assertEqual(loaded.interval_min, config.DEFAULT_INTERVAL_MIN)
            self.assertTrue(loaded.auto_enabled)


if __name__ == "__main__":
    unittest.main()
