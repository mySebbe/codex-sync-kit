import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codex_sync_kit.integrity import verify_snapshot
from codex_sync_kit.restore import restore_snapshot
from codex_sync_kit.scanner import ScanItem, scan, selected_items
from codex_sync_kit.snapshot import create_snapshot, latest_snapshot


def test_scan_snapshot_and_restore_sanitizes_config(tmp_path: Path) -> None:
    codex_home = tmp_path / "source" / ".codex"
    codex_home.mkdir(parents=True)
    (codex_home / "AGENTS.md").write_text("Use real umlauts: äöü.\n", encoding="utf-8")
    (codex_home / "config.toml").write_text(
        'model = "gpt-5"\napi_key = "secret"\n',
        encoding="utf-8",
    )
    (codex_home / "auth.json").write_text('{"token":"secret"}', encoding="utf-8")
    (codex_home / "skills").mkdir()
    (codex_home / "skills" / "demo.md").write_text("demo", encoding="utf-8")
    vault = tmp_path / "vault"

    items = selected_items(scan(codex_home, profile="safe"))
    snapshot = create_snapshot(
        vault_root=vault,
        codex_home=codex_home,
        items=items,
        profile="safe",
        include_risky=False,
        now=datetime(2026, 7, 7, 12, 0, tzinfo=UTC),
    )

    assert snapshot.name == "20260707T120000Z"
    assert latest_snapshot(vault) == "20260707T120000Z"
    assert (snapshot / "files" / "AGENTS.md").exists()
    assert not (snapshot / "files" / "auth.json").exists()
    sanitized = (snapshot / "files" / "config.toml").read_text(encoding="utf-8")
    assert "secret" not in sanitized
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"])
    assert verify_snapshot(vault, snapshot.name).valid

    target = tmp_path / "target" / ".codex"
    planned = restore_snapshot(
        vault_root=vault,
        snapshot="20260707T120000Z",
        codex_home=target,
        apply=True,
    )

    assert "AGENTS.md" in planned
    assert (target / "AGENTS.md").read_text(encoding="utf-8").startswith("Use real")


def test_scan_excludes_symlink_files(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    skills = codex_home / "skills"
    skills.mkdir()
    link = skills / "linked.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is not available in this environment.")

    items = scan(codex_home, profile="safe")

    linked = next(item for item in items if item.relative_path == "skills/linked.md")
    assert not linked.allowed
    assert linked.reason == "excluded-symlink"


def test_restore_rejects_blocked_manifest_paths(tmp_path: Path) -> None:
    snapshot = tmp_path / "vault" / "snapshots" / "s1"
    files = snapshot / "files"
    files.mkdir(parents=True)
    (files / "auth.json").write_text("{}", encoding="utf-8")
    (snapshot / "manifest.json").write_text(
        json.dumps({"files": [{"relative_path": "auth.json"}]}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="blocked restore path"):
        restore_snapshot(
            vault_root=tmp_path / "vault",
            snapshot="s1",
            codex_home=tmp_path / ".codex",
            apply=False,
            allow_legacy_unhashed=True,
        )


def test_restore_refuses_existing_symlink_target(tmp_path: Path) -> None:
    snapshot = tmp_path / "vault" / "snapshots" / "s1"
    files = snapshot / "files"
    files.mkdir(parents=True)
    (files / "AGENTS.md").write_text("safe", encoding="utf-8")
    (snapshot / "manifest.json").write_text(
        json.dumps({"files": [{"relative_path": "AGENTS.md"}]}),
        encoding="utf-8",
    )
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    target = codex_home / "AGENTS.md"
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is not available in this environment.")

    with pytest.raises(RuntimeError, match="symlink"):
        restore_snapshot(
            vault_root=tmp_path / "vault",
            snapshot="s1",
            codex_home=codex_home,
            apply=True,
        )

    assert outside.read_text(encoding="utf-8") == "outside"


def test_verify_and_restore_reject_tampered_snapshot(tmp_path: Path) -> None:
    codex_home = tmp_path / "source" / ".codex"
    codex_home.mkdir(parents=True)
    (codex_home / "AGENTS.md").write_text("trusted", encoding="utf-8")
    vault = tmp_path / "vault"
    snapshot = create_snapshot(
        vault_root=vault,
        codex_home=codex_home,
        items=selected_items(scan(codex_home, profile="safe")),
        profile="safe",
        include_risky=False,
        now=datetime(2026, 7, 7, 13, 0, tzinfo=UTC),
    )
    (snapshot / "files" / "AGENTS.md").write_text("tampered", encoding="utf-8")

    result = verify_snapshot(vault, snapshot.name)

    assert not result.valid
    assert any("mismatch" in error for error in result.errors)
    with pytest.raises(RuntimeError, match="integrity check failed"):
        restore_snapshot(
            vault_root=vault,
            snapshot=snapshot.name,
            codex_home=tmp_path / "target" / ".codex",
            apply=False,
        )


def test_verify_rejects_unlisted_files_and_unsafe_snapshot_ids(tmp_path: Path) -> None:
    snapshot = tmp_path / "vault" / "snapshots" / "s1"
    files = snapshot / "files"
    files.mkdir(parents=True)
    (files / "AGENTS.md").write_text("safe", encoding="utf-8")
    (snapshot / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "files": []}),
        encoding="utf-8",
    )

    result = verify_snapshot(tmp_path / "vault", "s1")

    assert not result.valid
    assert "unlisted snapshot file: AGENTS.md" in result.errors
    with pytest.raises(RuntimeError, match="Unsafe snapshot id"):
        verify_snapshot(tmp_path / "vault", "../outside")


def test_legacy_snapshot_remains_restorable_but_can_require_hashes(tmp_path: Path) -> None:
    snapshot = tmp_path / "vault" / "snapshots" / "s1"
    files = snapshot / "files"
    files.mkdir(parents=True)
    (files / "AGENTS.md").write_text("safe", encoding="utf-8")
    (snapshot / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "file_count": 1,
                "files": [{"relative_path": "AGENTS.md"}],
            }
        ),
        encoding="utf-8",
    )

    compatible = verify_snapshot(tmp_path / "vault", "s1")
    strict = verify_snapshot(tmp_path / "vault", "s1", require_hashes=True)

    assert compatible.valid
    assert compatible.warnings
    assert not strict.valid
    with pytest.raises(RuntimeError, match="integrity check failed"):
        restore_snapshot(
            vault_root=tmp_path / "vault",
            snapshot="s1",
            codex_home=tmp_path / "target" / ".codex",
            apply=False,
        )
    assert restore_snapshot(
        vault_root=tmp_path / "vault",
        snapshot="s1",
        codex_home=tmp_path / "target" / ".codex",
        apply=False,
        allow_legacy_unhashed=True,
    ) == ["AGENTS.md"]


def test_create_snapshot_rejects_relative_traversal_item(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    source = codex_home / "AGENTS.md"
    source.write_text("safe", encoding="utf-8")
    item = ScanItem("../../outside.txt", source, 4, True, False, "test")

    with pytest.raises(RuntimeError, match="unsafe path"):
        create_snapshot(
            vault_root=tmp_path / "vault",
            codex_home=codex_home,
            items=[item],
            profile="safe",
            include_risky=False,
        )

    assert not (tmp_path / "outside.txt").exists()


def test_create_snapshot_rejects_hardlinked_latest_marker(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "AGENTS.md").write_text("safe", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        os.link(outside, vault / "LATEST")
    except OSError as exc:
        pytest.skip(f"Hard links are unavailable: {exc}")

    with pytest.raises(RuntimeError, match="LATEST"):
        create_snapshot(
            vault_root=vault,
            codex_home=codex_home,
            items=selected_items(scan(codex_home, profile="safe")),
            profile="safe",
            include_risky=False,
        )

    assert outside.read_text(encoding="utf-8") == "outside"


def test_verify_rejects_hardlinked_snapshot_file(tmp_path: Path) -> None:
    snapshot = tmp_path / "vault" / "snapshots" / "s1"
    files = snapshot / "files"
    files.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        os.link(outside, files / "AGENTS.md")
    except OSError as exc:
        pytest.skip(f"Hard links are unavailable: {exc}")
    (snapshot / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "file_count": 1,
                "files": [{"relative_path": "AGENTS.md"}],
            }
        ),
        encoding="utf-8",
    )

    result = verify_snapshot(tmp_path / "vault", "s1")

    assert not result.valid
    assert any("unsafe" in error for error in result.errors)
