from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .rules import classify


def restore_snapshot(
    *,
    vault_root: Path,
    snapshot: str,
    codex_home: Path,
    apply: bool,
) -> list[str]:
    snapshot_root = vault_root / "snapshots" / snapshot
    files_root = snapshot_root / "files"
    manifest_path = snapshot_root / "manifest.json"
    if not files_root.exists():
        raise FileNotFoundError(f"Snapshot does not exist: {snapshot}")
    if not manifest_path.exists():
        raise RuntimeError(f"Snapshot manifest is missing: {snapshot}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_paths = {
        str(entry["relative_path"])
        for entry in manifest.get("files", [])
        if isinstance(entry, dict) and "relative_path" in entry
    }
    planned: list[str] = []
    for relative_text in sorted(manifest_paths):
        classification = classify(relative_text, "full", include_risky=True)
        if not classification.allowed:
            raise RuntimeError(f"Snapshot contains blocked restore path: {relative_text}")
        source = _safe_child(files_root, relative_text)
        if source.is_symlink() or not source.is_file():
            raise RuntimeError(f"Snapshot file is missing or unsafe: {relative_text}")
        target = _safe_child(codex_home, relative_text)
        planned.append(relative_text)
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.parent.resolve().is_relative_to(codex_home.resolve()):
                raise RuntimeError(f"Restore target escapes Codex home: {relative_text}")
            _ensure_safe_restore_target(codex_home, target, relative_text)
            _backup_existing(target)
            shutil.copy2(source, target)
    return planned


def _backup_existing(target: Path) -> None:
    if not target.exists():
        return
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = target.with_name(f"{target.name}.codex-sync-backup-{stamp}")
    shutil.copy2(target, backup)


def _ensure_safe_restore_target(root: Path, target: Path, relative_text: str) -> None:
    resolved_root = root.resolve()
    if target.is_symlink():
        raise RuntimeError(f"Restore target is a symlink: {relative_text}")
    if target.exists():
        if not target.resolve().is_relative_to(resolved_root):
            raise RuntimeError(f"Restore target escapes Codex home: {relative_text}")
        if not target.is_file():
            raise RuntimeError(f"Restore target is not a regular file: {relative_text}")
        if target.stat().st_nlink > 1:
            raise RuntimeError(f"Restore target is hard-linked: {relative_text}")


def _safe_child(root: Path, relative_text: str) -> Path:
    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"Unsafe snapshot path: {relative_text}")
    child = root / relative
    if root.exists() and child.exists() and not child.resolve().is_relative_to(root.resolve()):
        raise RuntimeError(f"Snapshot path escapes root: {relative_text}")
    return child
