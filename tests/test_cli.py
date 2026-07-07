from pathlib import Path

from codex_sync_kit.cli import RISK_CONFIRMATION, main


def test_scan_json_cli(tmp_path: Path, capsys) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "AGENTS.md").write_text("x", encoding="utf-8")

    rc = main(["scan", "--codex-home", str(codex_home), "--json"])

    assert rc == 0
    assert '"files_selected": 1' in capsys.readouterr().out


def test_include_risky_requires_confirmation(tmp_path: Path, capsys) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "tools").mkdir()
    (codex_home / "tools" / "x.py").write_text("print(1)", encoding="utf-8")

    rc = main(["scan", "--codex-home", str(codex_home), "--profile", "full", "--include-risky"])

    assert rc == 1
    assert RISK_CONFIRMATION in capsys.readouterr().err


def test_include_risky_with_confirmation(tmp_path: Path, capsys) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "tools").mkdir()
    (codex_home / "tools" / "x.py").write_text("print(1)", encoding="utf-8")

    rc = main(
        [
            "scan",
            "--codex-home",
            str(codex_home),
            "--profile",
            "full",
            "--include-risky",
            "--confirm-risky",
            RISK_CONFIRMATION,
        ]
    )

    assert rc == 0
    assert "+ tools/x.py" in capsys.readouterr().out
