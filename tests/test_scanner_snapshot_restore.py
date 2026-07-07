from datetime import UTC, datetime
from pathlib import Path

from codex_sync_kit.restore import restore_snapshot
from codex_sync_kit.scanner import scan, selected_items
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

    target = tmp_path / "target" / ".codex"
    planned = restore_snapshot(
        vault_root=vault,
        snapshot="20260707T120000Z",
        codex_home=target,
        apply=True,
    )

    assert "AGENTS.md" in planned
    assert (target / "AGENTS.md").read_text(encoding="utf-8").startswith("Use real")
