from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .config import redact_config_text
from .integrity import is_link_or_reparse, sha256_file
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
    snapshots_root = vault_root / "snapshots"
    if is_link_or_reparse(snapshots_root):
        raise RuntimeError("Vault snapshots directory is a link or reparse point")
    if snapshot_root.exists():
        if is_link_or_reparse(snapshot_root):
            raise RuntimeError(f"Snapshot directory is unsafe: {sid}")
        shutil.rmtree(snapshot_root)
    files_root.mkdir(parents=True, exist_ok=True)

    root = codex_home.resolve()
    copied: list[dict[str, object]] = []
    for item in items:
        relative = Path(item.relative_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise RuntimeError(f"Refusing to snapshot unsafe path: {item.relative_path}")
        if (
            is_link_or_reparse(item.absolute_path)
            or not item.absolute_path.is_file()
            or item.absolute_path.stat().st_nlink > 1
            or not item.absolute_path.resolve().is_relative_to(root)
        ):
            raise RuntimeError(f"Refusing to snapshot unsafe path: {item.relative_path}")
        destination = files_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.parent.resolve().is_relative_to(files_root.resolve()):
            raise RuntimeError(f"Snapshot destination escapes files root: {item.relative_path}")
        if item.relative_path == "config.toml":
            text = item.absolute_path.read_text(encoding="utf-8", errors="replace")
            destination.write_text(redact_config_text(text), encoding="utf-8")
        else:
            shutil.copy2(item.absolute_path, destination)
        copied.append(
            asdict(item)
            | {
                "absolute_path": str(item.absolute_path),
                "snapshot_size": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        )

    manifest = {
        "schema_version": 2,
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
    _write_latest(vault_root, latest, sid)
    return snapshot_root


def _write_latest(vault_root: Path, latest: Path, sid: str) -> None:
    if is_link_or_reparse(latest):
        raise RuntimeError("LATEST marker is a link or reparse point")
    if latest.exists() and (not latest.is_file() or latest.stat().st_nlink > 1):
        raise RuntimeError("LATEST marker is not an unlinked regular file")
    if not latest.parent.resolve().is_relative_to(vault_root.resolve()):
        raise RuntimeError("LATEST marker escapes vault root")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=latest.parent,
        prefix=".LATEST.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(sid + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, latest)
    finally:
        temporary.unlink(missing_ok=True)


def list_snapshots(vault_root: Path) -> list[str]:
    root = vault_root / "snapshots"
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def latest_snapshot(vault_root: Path) -> str | None:
    marker = vault_root / "LATEST"
    if marker.exists():
        if is_link_or_reparse(marker) or not marker.is_file() or marker.stat().st_nlink > 1:
            raise RuntimeError("LATEST marker is unsafe")
        value = marker.read_text(encoding="utf-8").strip()
        if value:
            return value
    snapshots = list_snapshots(vault_root)
    return snapshots[-1] if snapshots else None
