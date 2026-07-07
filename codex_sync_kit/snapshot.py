from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .config import redact_config_text
from .scanner import ScanItem


def snapshot_id(now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def create_snapshot(
    *,
    vault_root: Path,
    codex_home: Path,
    items: list[ScanItem],
    profile: str,
    include_risky: bool,
    now: datetime | None = None,
) -> Path:
    sid = snapshot_id(now)
    snapshot_root = vault_root / "snapshots" / sid
    files_root = snapshot_root / "files"
    if snapshot_root.exists():
        shutil.rmtree(snapshot_root)
    files_root.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, object]] = []
    for item in items:
        destination = files_root / item.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if item.relative_path == "config.toml":
            text = item.absolute_path.read_text(encoding="utf-8", errors="replace")
            destination.write_text(redact_config_text(text), encoding="utf-8")
        else:
            shutil.copy2(item.absolute_path, destination)
        copied.append(asdict(item) | {"absolute_path": str(item.absolute_path)})

    manifest = {
        "schema_version": 1,
        "snapshot_id": sid,
        "created_at": datetime.now(UTC).isoformat(),
        "codex_home": str(codex_home),
        "profile": profile,
        "include_risky": include_risky,
        "file_count": len(copied),
        "files": copied,
    }
    (snapshot_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    latest = vault_root / "LATEST"
    latest.write_text(sid + "\n", encoding="utf-8")
    return snapshot_root


def list_snapshots(vault_root: Path) -> list[str]:
    root = vault_root / "snapshots"
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def latest_snapshot(vault_root: Path) -> str | None:
    marker = vault_root / "LATEST"
    if marker.exists():
        value = marker.read_text(encoding="utf-8").strip()
        if value:
            return value
    snapshots = list_snapshots(vault_root)
    return snapshots[-1] if snapshots else None
