"""Headless smoke test for the Qt window and its backup wiring."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from bonfire import config
from bonfire.store import KIND_BOSS, KIND_MANUAL
from bonfire.ui.theme import apply_theme
from bonfire.ui.window import MainWindow


class WindowSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.env = {
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_CONFIG_HOME": str(root / "config"),
        }
        self._old_env = {key: os.environ.get(key) for key in self.env}
        os.environ.update(self.env)
        self.save = root / "save" / "DRAKS0005.sl2"
        self.save.parent.mkdir()
        self.save.write_bytes(b"BND4" + b"ember" * 1500)
        self.settings = config.Settings(
            save_file=str(self.save),
            auto_enabled=False,
            interval_min=1,
            max_backups=5,
        )

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def test_backup_selection_and_retention(self) -> None:
        window = MainWindow(self.settings)
        window.show()
        self.app.processEvents()
        self.assertEqual(window.table.topLevelItemCount(), 0)
        self.assertFalse(window.restore_btn.isEnabled())

        window._manual_backup(KIND_BOSS)
        self.app.processEvents()
        self.assertEqual(window.table.topLevelItemCount(), 1)
        backup = window.vault.latest()
        self.assertEqual(backup.kind, KIND_BOSS)
        self.assertTrue(backup.pinned)
        self.assertEqual(window._selected_id, backup.id)
        self.assertIn("SHA-256", window.detail_hash.text())

        for _ in range(2):
            window._manual_backup(KIND_MANUAL)
        self.app.processEvents()
        self.assertEqual(window.table.topLevelItemCount(), 3)

        window.retention_spin.setValue(1)
        self.app.processEvents()
        unpinned = [b for b in window.vault.list() if not b.pinned]
        self.assertEqual(len(unpinned), 1)
        self.assertTrue(any(b.pinned for b in window.vault.list()))

        # An unchanged automatic backup is suppressed.
        before = window.table.topLevelItemCount()
        window._auto_backup()
        self.app.processEvents()
        self.assertEqual(window.table.topLevelItemCount(), before)
        self.assertIn("unchanged", window.auto_note.text())

        # Capturing after a change adds a snapshot (retention=1 keeps the newest
        # unpinned auto, so the older manual is rotated out).
        self.save.write_bytes(b"BND4" + b"newer" * 1500)
        window._auto_backup()
        self.app.processEvents()
        self.assertEqual(window.table.topLevelItemCount(), 2)
        self.assertEqual(window.vault.latest().kind, "auto")

        window.close()

    def test_restore_through_vault_used_by_ui(self) -> None:
        window = MainWindow(self.settings)
        window.show()
        self.app.processEvents()
        original = self.save.read_bytes()
        window._manual_backup(KIND_BOSS)
        self.app.processEvents()
        chosen = window.vault.latest()

        self.save.write_bytes(b"BND4" + b"later" * 1500)
        from bonfire.store import restore_backup

        safety = restore_backup(chosen, self.save, vault=window.vault)
        self.assertEqual(self.save.read_bytes(), original)
        self.assertIsNotNone(safety)
        self.assertTrue(safety.pinned)
        window.close()


if __name__ == "__main__":
    unittest.main()
