"""Command line interface — useful for quick snapshots and scripting."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, detect, system
from .paths import VERSION
from .store import KIND_BOSS, KIND_MANUAL, Vault, restore_backup


def _resolve_save(settings: config.Settings) -> Path | None:
    if settings.save_file:
        candidate = Path(settings.save_file).expanduser()
        if candidate.is_file():
            return candidate
    result = detect.detect()
    return result.save_file


def _cmd_detect(_args: argparse.Namespace) -> int:
    result = detect.detect()
    if not result.found:
        print("No save found.")
        for note in result.notes:
            print(f"  · {note}")
        return 1
    print(f"Save file: {result.save_file}")
    print(f"Source:    {result.source}")
    if len(result.candidates) > 1:
        print("Other candidates:")
        for cand in result.candidates[1:]:
            print(f"  · {cand.save_file}  ({cand.source})")
    return 0


def _cmd_backup(args: argparse.Namespace) -> int:
    settings = config.load()
    save = Path(args.file).expanduser() if args.file else _resolve_save(settings)
    if not save or not save.is_file():
        print("No save file found. Use --file or run `bonfire detect`.", file=sys.stderr)
        return 1
    kind = KIND_BOSS if args.kind == "boss" else KIND_MANUAL
    backup = Vault().create(save, kind=kind, note=args.note)
    removed = Vault().prune(settings.max_backups)
    print(f"Created {backup.id} ({backup.size} bytes)")
    for item in removed:
        print(f"Pruned  {item.id}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    backups = Vault().list()
    if args.json:
        import json

        print(json.dumps([
            {
                "id": b.id,
                "created_at": b.created_at.isoformat(),
                "kind": b.kind,
                "note": b.note,
                "size": b.size,
                "pinned": b.pinned,
                "sha256": b.sha256,
            }
            for b in backups
        ], indent=2))
        return 0
    if not backups:
        print("The vault is empty.")
        return 0
    for b in backups:
        pin = "◆" if b.pinned else " "
        note = f"  {b.note}" if b.note else ""
        print(f"{pin} {b.created_at:%Y-%m-%d %H:%M:%S}  {b.kind:<11} {b.size / 1048576:5.2f} MB  {b.id}{note}")
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    settings = config.load()
    vault = Vault()
    backup = vault.latest() if args.id == "latest" else vault.get(args.id)
    if backup is None:
        print(f"No backup with id {args.id!r}.", file=sys.stderr)
        return 1
    save = _resolve_save(settings)
    if not save:
        print("No save file found to restore over.", file=sys.stderr)
        return 1

    if system.game_running():
        print("Dark Souls: Remastered appears to be running — close it before restoring.", file=sys.stderr)
        return 2

    if not args.yes:
        print(f"About to replace:\n  {save}\nwith:\n  {backup.id} ({backup.timestamp_text})")
        print("A pinned safety snapshot of the current save will be created first.")
        try:
            answer = input("Continue? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            print("Cancelled.")
            return 1

    try:
        safety = restore_backup(backup, save, vault=vault)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Restore failed: {exc}", file=sys.stderr)
        return 1
    print(f"Restored {backup.id} → {save}")
    if safety:
        print(f"Safety snapshot: {safety.id}")
    return 0


def _cmd_prune(args: argparse.Namespace) -> int:
    settings = config.load()
    removed = Vault().prune(args.keep or settings.max_backups)
    print(f"Removed {len(removed)} snapshot(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bonfire", description="Dark Souls: Remastered save vault")
    parser.add_argument("--version", action="version", version=f"Bonfire {VERSION}")
    sub = parser.add_subparsers(dest="command")

    p_gui = sub.add_parser("gui", help="open the graphical interface (default)")
    p_gui.set_defaults(func=lambda _a: _gui())

    p_detect = sub.add_parser("detect", help="locate the save file")
    p_detect.set_defaults(func=_cmd_detect)

    p_backup = sub.add_parser("backup", help="take a snapshot now")
    p_backup.add_argument("--kind", choices=["manual", "boss"], default="manual")
    p_backup.add_argument("--note", default="")
    p_backup.add_argument("--file", help="explicit save file path")
    p_backup.set_defaults(func=_cmd_backup)

    p_list = sub.add_parser("list", help="list snapshots")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=_cmd_list)

    p_restore = sub.add_parser("restore", help="restore a snapshot (id or 'latest')")
    p_restore.add_argument("id")
    p_restore.add_argument("--yes", action="store_true")
    p_restore.set_defaults(func=_cmd_restore)

    p_prune = sub.add_parser("prune", help="apply the retention limit")
    p_prune.add_argument("--keep", type=int)
    p_prune.set_defaults(func=_cmd_prune)
    return parser


def _gui() -> int:
    from .ui.app import run

    return run()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        return _gui()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
