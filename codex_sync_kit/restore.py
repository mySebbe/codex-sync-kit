from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path


def restore_snapshot(
    *,
    vault_root: Path,
    snapshot: str,
    codex_home: Path,
    apply: bool,
) -> list[str]:
    files_root = vault_root / "snapshots" / snapshot / "files"
    if not files_root.exists():
        raise FileNotFoundError(f"Snapshot does not exist: {snapshot}")

    planned: list[str] = []
    for source in sorted(files_root.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(files_root)
        target = codex_home / relative
        planned.append(relative.as_posix())
        if apply:
            _backup_existing(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return planned


def _backup_existing(target: Path) -> None:
    if not target.exists():
        return
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = target.with_name(f"{target.name}.codex-sync-backup-{stamp}")
    shutil.copy2(target, backup)
