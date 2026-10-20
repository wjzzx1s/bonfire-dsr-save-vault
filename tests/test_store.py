from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bonfire.paths import SAVE_FILENAME
from bonfire.store import (
    KIND_AUTO,
    KIND_BOSS,
    KIND_MANUAL,
    KIND_SAFETY,
    RestoreError,
    Vault,
    restore_backup,
    sha256_file,
)


class VaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.save = self.root / "live" / SAVE_FILENAME
        self.save.parent.mkdir()
        self.save.write_bytes(b"BND4" + b"initial" * 800)
        self.vault = Vault(self.root / "vault")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_snapshot_records_metadata_and_hash(self) -> None:
        backup = self.vault.create(self.save, kind=KIND_MANUAL, note="before Gargoyles")

        self.assertEqual(backup.kind, KIND_MANUAL)
        self.assertEqual(backup.note, "before Gargoyles")
        self.assertFalse(backup.pinned)
        self.assertTrue(backup.file.is_file())
        self.assertEqual(backup.sha256, sha256_file(self.save))
        self.assertEqual(backup.size, self.save.stat().st_size)
        self.assertEqual(self.vault.get(backup.id).id, backup.id)
        self.assertTrue(self.vault.verify(backup))

    def test_ids_are_unique_within_one_second(self) -> None:
        ids = {self.vault.create(self.save, note=str(i)).id for i in range(5)}
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(self.vault.list()), 5)

    def test_rotation_keeps_newest_unpinned_and_spares_pinned(self) -> None:
        boss = self.vault.create(self.save, kind=KIND_BOSS, note="Ornstein")
        autos = [self.vault.create(self.save, kind=KIND_AUTO, note=str(i)) for i in range(4)]

        removed = self.vault.prune(2)

        remaining = {b.id for b in self.vault.list()}
        self.assertEqual(len(removed), 2)
        self.assertIn(boss.id, remaining)
        self.assertTrue(boss.pinned)
        self.assertIn(autos[-1].id, remaining)
        self.assertIn(autos[-2].id, remaining)
        self.assertNotIn(autos[0].id, remaining)

    def test_verify_detects_corruption(self) -> None:
        backup = self.vault.create(self.save)
        backup.file.write_bytes(b"BND4tampered")

        self.assertFalse(self.vault.verify(backup))

    def test_restore_replaces_save_and_creates_pinned_safety_copy(self) -> None:
        original = self.save.read_bytes()
        backup = self.vault.create(self.save, note="clean state")
        self.save.write_bytes(b"BND4" + b"progress" * 900)

        safety = restore_backup(backup, self.save, vault=self.vault)

        self.assertEqual(self.save.read_bytes(), original)
        self.assertIsNotNone(safety)
        self.assertEqual(safety.kind, KIND_SAFETY)
        self.assertTrue(safety.pinned)
        self.assertEqual(safety.file.read_bytes(), b"BND4" + b"progress" * 900)
        self.assertEqual(len(self.vault.list()), 2)

    def test_restore_refuses_corrupted_backup(self) -> None:
        backup = self.vault.create(self.save)
        backup.file.write_bytes(b"BND4broken")

        with self.assertRaises(RestoreError):
            restore_backup(backup, self.save, vault=self.vault)
        self.assertNotEqual(self.save.read_bytes(), b"BND4broken")

    def test_update_note_persists(self) -> None:
        backup = self.vault.create(self.save)
        self.vault.update_note(backup, "Bell Gargoyles, attempt 3")

        self.assertEqual(self.vault.get(backup.id).note, "Bell Gargoyles, attempt 3")

    def test_delete_removes_snapshot_folder(self) -> None:
        backup = self.vault.create(self.save)
        self.vault.delete(backup)

        self.assertEqual(self.vault.list(), [])
        self.assertFalse(backup.directory.exists())


if __name__ == "__main__":
    unittest.main()
