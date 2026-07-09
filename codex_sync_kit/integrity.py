from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

MAX_MANIFEST_BYTES = 10 * 1024 * 1024
MAX_SNAPSHOT_FILES = 20_000
MAX_SNAPSHOT_BYTES = 1024 * 1024 * 1024
HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class SnapshotVerification:
    snapshot: str
    schema_version: int | None
    valid: bool
    integrity_protected: bool
    verified_files: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(attributes & reparse_flag)
    except FileNotFoundError:
        return False


def verify_snapshot(
    vault_root: Path,
    snapshot: str,
    *,
    require_hashes: bool = False,
) -> SnapshotVerification:
    errors: list[str] = []
    warnings: list[str] = []
    snapshot_root = _snapshot_root(vault_root, snapshot)
    files_root = snapshot_root / "files"
    manifest_path = snapshot_root / "manifest.json"

    if is_link_or_reparse(files_root) or not files_root.is_dir():
        errors.append("snapshot files directory is missing")
    if (
        is_link_or_reparse(manifest_path)
        or not manifest_path.is_file()
        or manifest_path.stat().st_nlink > 1
    ):
        errors.append("snapshot manifest is missing")
    if errors:
        return SnapshotVerification(snapshot, None, False, False, 0, errors, warnings)

    try:
        manifest_size = manifest_path.stat().st_size
    except OSError as exc:
        errors.append(f"cannot stat snapshot manifest: {exc}")
        return SnapshotVerification(snapshot, None, False, False, 0, errors, warnings)
    if manifest_size > MAX_MANIFEST_BYTES:
        errors.append(f"snapshot manifest exceeds {MAX_MANIFEST_BYTES} bytes")
        return SnapshotVerification(snapshot, None, False, False, 0, errors, warnings)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read snapshot manifest: {exc}")
        return SnapshotVerification(snapshot, None, False, False, 0, errors, warnings)
    if not isinstance(manifest, dict):
        errors.append("snapshot manifest must be a JSON object")
        return SnapshotVerification(snapshot, None, False, False, 0, errors, warnings)

    schema = manifest.get("schema_version", 1)
    if not isinstance(schema, int) or schema not in {1, 2}:
        errors.append(f"unsupported snapshot schema version: {schema!r}")
        return SnapshotVerification(snapshot, None, False, False, 0, errors, warnings)
    if manifest.get("snapshot_id") not in {None, snapshot}:
        errors.append("snapshot id does not match its directory")

    entries = manifest.get("files")
    if not isinstance(entries, list):
        errors.append("snapshot manifest files must be a list")
        return SnapshotVerification(snapshot, schema, False, schema >= 2, 0, errors, warnings)
    if len(entries) > MAX_SNAPSHOT_FILES:
        errors.append(f"snapshot manifest exceeds {MAX_SNAPSHOT_FILES} files")
        return SnapshotVerification(snapshot, schema, False, schema >= 2, 0, errors, warnings)
    if manifest.get("file_count") not in {None, len(entries)}:
        errors.append("snapshot manifest file_count does not match files")

    listed: set[str] = set()
    verified_files = 0
    declared_bytes = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"manifest entry {index} is not an object")
            continue
        relative_text = entry.get("relative_path")
        if not isinstance(relative_text, str) or not relative_text:
            errors.append(f"manifest entry {index} has no valid relative_path")
            continue
        normalized = _normalized_relative(relative_text)
        if normalized is None:
            errors.append(f"unsafe snapshot path: {relative_text}")
            continue
        if normalized in listed:
            errors.append(f"duplicate snapshot path: {normalized}")
            continue
        listed.add(normalized)
        source = files_root / Path(normalized)
        if is_link_or_reparse(source) or not source.is_file() or source.stat().st_nlink > 1:
            errors.append(f"snapshot file is missing or unsafe: {normalized}")
            continue
        if not source.resolve().is_relative_to(files_root.resolve()):
            errors.append(f"snapshot file escapes files root: {normalized}")
            continue

        if schema >= 2:
            expected_size = entry.get("snapshot_size")
            expected_hash = entry.get("sha256")
            if not isinstance(expected_size, int) or expected_size < 0:
                errors.append(f"snapshot size is missing or invalid: {normalized}")
                continue
            declared_bytes += expected_size
            if declared_bytes > MAX_SNAPSHOT_BYTES:
                errors.append(f"snapshot exceeds {MAX_SNAPSHOT_BYTES} total bytes")
                break
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                errors.append(f"snapshot hash is missing or invalid: {normalized}")
                continue
            if source.stat().st_size != expected_size:
                errors.append(f"snapshot size mismatch: {normalized}")
                continue
            if sha256_file(source) != expected_hash.lower():
                errors.append(f"snapshot hash mismatch: {normalized}")
                continue
        verified_files += 1

    actual = _actual_files(files_root, errors)
    for unexpected in sorted(actual - listed):
        errors.append(f"unlisted snapshot file: {unexpected}")
    for missing in sorted(listed - actual):
        if f"snapshot file is missing or unsafe: {missing}" not in errors:
            errors.append(f"snapshot file is missing or unsafe: {missing}")

    integrity_protected = schema >= 2
    if not integrity_protected:
        warnings.append("legacy schema has no per-file hashes")
        if require_hashes:
            errors.append("snapshot does not provide per-file integrity hashes")
    return SnapshotVerification(
        snapshot,
        schema,
        not errors,
        integrity_protected,
        verified_files,
        errors,
        warnings,
    )


def _snapshot_root(vault_root: Path, snapshot: str) -> Path:
    relative = Path(snapshot)
    if not snapshot or relative.is_absolute() or len(relative.parts) != 1 or ".." in relative.parts:
        raise RuntimeError(f"Unsafe snapshot id: {snapshot}")
    snapshots_root = vault_root / "snapshots"
    if is_link_or_reparse(snapshots_root):
        raise RuntimeError("Vault snapshots directory is a link or reparse point")
    candidate = snapshots_root / relative
    if is_link_or_reparse(candidate):
        raise RuntimeError(f"Snapshot directory is a link or reparse point: {snapshot}")
    if (
        snapshots_root.exists()
        and candidate.exists()
        and not candidate.resolve().is_relative_to(snapshots_root.resolve())
    ):
        raise RuntimeError(f"Snapshot path escapes vault: {snapshot}")
    return candidate


def _normalized_relative(relative_text: str) -> str | None:
    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        return None
    normalized = relative.as_posix()
    return normalized if normalized not in {"", "."} else None


def _actual_files(files_root: Path, errors: list[str]) -> set[str]:
    actual: set[str] = set()
    total_bytes = 0
    for current, directories, filenames in os.walk(files_root, followlinks=False):
        current_path = Path(current)
        for directory in list(directories):
            path = current_path / directory
            if is_link_or_reparse(path):
                relative = path.relative_to(files_root).as_posix()
                errors.append(
                    f"snapshot contains a linked directory: {relative}"
                )
                directories.remove(directory)
        for filename in filenames:
            path = current_path / filename
            relative = path.relative_to(files_root).as_posix()
            if is_link_or_reparse(path) or not path.is_file() or path.stat().st_nlink > 1:
                errors.append(f"snapshot contains an unsafe file: {relative}")
                continue
            actual.add(relative)
            total_bytes += path.stat().st_size
            if len(actual) > MAX_SNAPSHOT_FILES:
                errors.append(f"snapshot contains more than {MAX_SNAPSHOT_FILES} actual files")
                return actual
            if total_bytes > MAX_SNAPSHOT_BYTES:
                errors.append(f"snapshot contains more than {MAX_SNAPSHOT_BYTES} actual bytes")
                return actual
    return actual
