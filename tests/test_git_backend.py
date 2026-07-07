from pathlib import Path

import pytest

from codex_sync_kit.config import AppConfig
from codex_sync_kit.git_backend import (
    CommandResult,
    commit_and_push,
    ensure_local_git_identity,
    ensure_private_repo,
    ensure_vault_remote_matches,
    init_vault_repo_if_empty,
)


def test_existing_public_vault_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("codex_sync_kit.git_backend.require_tools", lambda: None)

    def fake_run(args: list[str], *, cwd=None, check: bool = True) -> CommandResult:
        return CommandResult(tuple(args), 0, '{"visibility":"PUBLIC"}', "")

    monkeypatch.setattr("codex_sync_kit.git_backend.run", fake_run)

    with pytest.raises(RuntimeError, match="must be private"):
        ensure_private_repo(AppConfig(owner="me", vault="vault"))


def test_existing_vault_remote_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(args: list[str], *, cwd=None, check: bool = True) -> CommandResult:
        return CommandResult(tuple(args), 0, '{"nameWithOwner":"other/repo"}', "")

    monkeypatch.setattr("codex_sync_kit.git_backend.run", fake_run)

    with pytest.raises(RuntimeError, match="expected me/vault"):
        ensure_vault_remote_matches(tmp_path, AppConfig(owner="me", vault="vault"))


def test_missing_git_identity_sets_github_noreply(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(args: list[str], *, cwd=None, check: bool = True) -> CommandResult:
        calls.append(tuple(args))
        if args == ["git", "config", "user.email"]:
            return CommandResult(tuple(args), 1, "", "")
        if args == ["gh", "api", "user", "--jq", ".id"]:
            return CommandResult(tuple(args), 0, "123\n", "")
        if args == ["gh", "api", "user", "--jq", ".login"]:
            return CommandResult(tuple(args), 0, "octo\n", "")
        return CommandResult(tuple(args), 0, "", "")

    monkeypatch.setattr("codex_sync_kit.git_backend.run", fake_run)

    ensure_local_git_identity(tmp_path)

    assert ("git", "config", "user.name", "octo") in calls
    assert ("git", "config", "user.email", "123+octo@users.noreply.github.com") in calls


def test_empty_vault_switches_to_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(args: list[str], *, cwd=None, check: bool = True) -> CommandResult:
        calls.append(tuple(args))
        if args == ["git", "rev-parse", "--verify", "HEAD"]:
            return CommandResult(tuple(args), 1, "", "")
        return CommandResult(tuple(args), 0, "", "")

    monkeypatch.setattr("codex_sync_kit.git_backend.run", fake_run)

    init_vault_repo_if_empty(tmp_path)

    assert ("git", "checkout", "-B", "main") in calls


def test_vault_push_always_targets_origin_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def fake_run(args: list[str], *, cwd=None, check: bool = True) -> CommandResult:
        calls.append(tuple(args))
        if args == ["git", "status", "--porcelain"]:
            return CommandResult(tuple(args), 0, " M README.md\n", "")
        if args == ["git", "config", "user.email"]:
            return CommandResult(tuple(args), 0, "me@example.com\n", "")
        return CommandResult(tuple(args), 0, "", "")

    monkeypatch.setattr("codex_sync_kit.git_backend.run", fake_run)

    assert commit_and_push(tmp_path, "test")
    assert ("git", "push", "-u", "origin", "HEAD:main") in calls
    assert ("git", "push") not in calls
