import pytest

from codex_sync_kit.config import AppConfig
from codex_sync_kit.git_backend import CommandResult, ensure_private_repo


def test_existing_public_vault_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("codex_sync_kit.git_backend.require_tools", lambda: None)

    def fake_run(args: list[str], *, cwd=None, check: bool = True) -> CommandResult:
        return CommandResult(tuple(args), 0, '{"visibility":"PUBLIC"}', "")

    monkeypatch.setattr("codex_sync_kit.git_backend.run", fake_run)

    with pytest.raises(RuntimeError, match="must be private"):
        ensure_private_repo(AppConfig(owner="me", vault="vault"))
