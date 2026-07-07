from pathlib import Path

import pytest

from codex_sync_kit.config import AppConfig
from codex_sync_kit.git_backend import CommandResult, ensure_local_git_identity, ensure_private_repo


def test_existing_public_vault_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("codex_sync_kit.git_backend.require_tools", lambda: None)

    def fake_run(args: list[str], *, cwd=None, check: bool = True) -> CommandResult:
        return CommandResult(tuple(args), 0, '{"visibility":"PUBLIC"}', "")

    monkeypatch.setattr("codex_sync_kit.git_backend.run", fake_run)

    with pytest.raises(RuntimeError, match="must be private"):
        ensure_private_repo(AppConfig(owner="me", vault="vault"))


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
