"""Backup vault: immutable snapshots, rotation, verification and safe restore."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .paths import SAVE_FILENAME, backups_dir

KIND_AUTO = "auto"
KIND_MANUAL = "manual"
KIND_BOSS = "boss"
KIND_SAFETY = "pre-restore"

KIND_LABELS = {
    KIND_AUTO: "Automatic",
    KIND_MANUAL: "Manual",
    KIND_BOSS: "Boss",
    KIND_SAFETY: "Safety",
}

META_NAME = "meta.json"


class VaultError(RuntimeError):
    pass


class RestoreError(RuntimeError):
    pass


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


@dataclass
class Backup:
    id: str
    created_at: datetime
    kind: str
    note: str
    size: int
    sha256: str
    source_path: str
    source_mtime: float | None
    pinned: bool
    directory: Path
    filename: str = SAVE_FILENAME

    @property
    def file(self) -> Path:
        return self.directory / self.filename

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind.title())

    @property
    def timestamp_text(self) -> str:
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")


def _write_json_atomic(path: Path, payload: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".meta-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Vault:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else backups_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ read
    def list(self) -> list[Backup]:
        """All valid snapshots, newest first. Incomplete folders are ignored."""
        out: list[Backup] = []
        try:
            entries = list(self.root.iterdir())
        except OSError:
            return out
        for entry in entries:
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            backup = self._read(entry)
            if backup is not None:
                out.append(backup)
        out.sort(key=lambda b: (b.created_at, b.id), reverse=True)
        return out

    def _read(self, directory: Path) -> Backup | None:
        meta_path = directory / META_NAME
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(meta["created_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        filename = meta.get("filename", SAVE_FILENAME)
        if not (directory / filename).is_file():
            return None
        try:
            size = int(meta.get("size", (directory / filename).stat().st_size))
        except (TypeError, ValueError, OSError):
            size = 0
        return Backup(
            id=str(meta.get("id", directory.name)),
            created_at=created,
            kind=str(meta.get("kind", KIND_MANUAL)),
            note=str(meta.get("note", "")),
            size=size,
            sha256=str(meta.get("sha256", "")),
            source_path=str(meta.get("source_path", "")),
            source_mtime=meta.get("source_mtime"),
            pinned=bool(meta.get("pinned", False)),
            directory=directory,
            filename=filename,
        )

    def get(self, backup_id: str) -> Backup | None:
        for backup in self.list():
            if backup.id == backup_id:
                return backup
        return None

    def latest(self) -> Backup | None:
        items = self.list()
        return items[0] if items else None

    def total_size(self) -> int:
        return sum(b.size for b in self.list())

    def verify(self, backup: Backup) -> bool:
        try:
            if not backup.file.is_file() or backup.file.stat().st_size != backup.size:
                return False
            return sha256_file(backup.file) == backup.sha256
        except OSError:
            return False

    # ----------------------------------------------------------------- write
    def _unique_id(self, created: datetime, kind: str) -> str:
        base = f"{created.strftime('%Y%m%d-%H%M%S')}-{kind}"
        candidate = base
        counter = 2
        while (self.root / candidate).exists() or (self.root / f".incoming-{candidate}").exists():
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    def create(
        self,
        source: Path,
        kind: str = KIND_MANUAL,
        note: str = "",
        pinned: bool | None = None,
    ) -> Backup:
        source = Path(source)
        if not source.is_file():
            raise VaultError(f"Save file not found: {source}")
        if pinned is None:
            pinned = kind in (KIND_BOSS, KIND_SAFETY)

        created = datetime.now().astimezone()
        backup_id = self._unique_id(created, kind)
        incoming = self.root / f".incoming-{backup_id}"
        try:
            incoming.mkdir(parents=True)
            target = incoming / SAVE_FILENAME
            before = source.stat()
            source_hash = sha256_file(source)
            with open(source, "rb") as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            after = source.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise VaultError(
                    "The save file changed while it was being copied, so the snapshot was "
                    "discarded. Try again once the game has finished saving."
                )
            if sha256_file(target) != source_hash:
                raise VaultError("Copy verification failed — the snapshot does not match the save.")
            stat = source.stat()
            meta = {
                "version": 1,
                "id": backup_id,
                "created_at": created.isoformat(timespec="microseconds"),
                "kind": kind,
                "note": note.strip(),
                "pinned": bool(pinned),
                "size": target.stat().st_size,
                "sha256": source_hash,
                "source_path": str(source),
                "source_mtime": stat.st_mtime,
                "filename": SAVE_FILENAME,
            }
            _write_json_atomic(incoming / META_NAME, meta)
            final = self.root / backup_id
            os.replace(incoming, final)
        except Exception:
            shutil.rmtree(incoming, ignore_errors=True)
            raise

        return Backup(
            id=backup_id,
            created_at=created,
            kind=kind,
            note=note.strip(),
            size=meta["size"],
            sha256=source_hash,
            source_path=str(source),
            source_mtime=meta["source_mtime"],
            pinned=bool(pinned),
            directory=final,
        )

    def update_note(self, backup: Backup, note: str) -> Backup:
        meta_path = backup.directory / META_NAME
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise VaultError(f"Cannot read backup metadata: {exc}") from exc
        meta["note"] = note.strip()
        _write_json_atomic(meta_path, meta)
        backup.note = note.strip()
        return backup

    def delete(self, backup: Backup) -> None:
        shutil.rmtree(backup.directory, ignore_errors=False)

    def prune(self, max_keep: int) -> list[Backup]:
        """Delete the oldest unpinned snapshots beyond *max_keep*."""
        max_keep = max(1, int(max_keep))
        unpinned = [b for b in self.list() if not b.pinned]
        doomed = unpinned[max_keep:]
        removed: list[Backup] = []
        for backup in doomed:
            try:
                self.delete(backup)
                removed.append(backup)
            except OSError:
                continue
        return removed

    def cleanup_incoming(self, older_than_s: float = 3600) -> None:
        """Remove leftovers from interrupted snapshots."""
        now = datetime.now().timestamp()
        for entry in self.root.glob(".incoming-*"):
            try:
                if now - entry.stat().st_mtime > older_than_s:
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                pass


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def restore_backup(
    backup: Backup,
    target: Path,
    vault: Vault | None = None,
    make_safety: bool = True,
) -> Backup | None:
    """Replace *target* with *backup*, after snapshotting the current save.

    Returns the safety snapshot that was created, if any.  The caller is
    responsible for checking that the game is not running.
    """
    target = Path(target)
    if not backup.file.is_file():
        raise RestoreError("The selected backup file is missing from the vault.")
    if not backup.sha256 or sha256_file(backup.file) != backup.sha256:
        raise RestoreError("This backup failed its integrity check and was not restored.")

    vault = vault or Vault()
    safety: Backup | None = None
    if make_safety and target.is_file():
        safety = vault.create(
            target,
            kind=KIND_SAFETY,
            note=f"Automatic safety copy before restoring {backup.id}",
            pinned=True,
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.bonfire-tmp")
    try:
        with open(backup.file, "rb") as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        if sha256_file(tmp) != backup.sha256:
            raise RestoreError("The written file failed verification; your save was left untouched.")
        os.replace(tmp, target)
        _fsync_dir(target.parent)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise

    if sha256_file(target) != backup.sha256:
        raise RestoreError("The restored file could not be verified after writing.")
    return safety
