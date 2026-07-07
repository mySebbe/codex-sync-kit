from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    def __init__(self, result: CommandResult) -> None:
        self.result = result
        joined = " ".join(result.args)
        super().__init__(f"Command failed ({result.returncode}): {joined}\n{result.stderr}")


def require_tools() -> None:
    missing = [tool for tool in ("git", "gh") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required tool(s): {', '.join(missing)}")


def run(args: list[str], *, cwd: Path | None = None, check: bool = True) -> CommandResult:
    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    result = CommandResult(tuple(args), proc.returncode, proc.stdout, proc.stderr)
    if check and proc.returncode != 0:
        raise CommandError(result)
    return result


def ensure_private_repo(config: AppConfig, *, create: bool = True) -> None:
    require_tools()
    view = run(
        ["gh", "repo", "view", config.repo, "--json", "nameWithOwner,visibility"],
        check=False,
    )
    if view.returncode == 0:
        visibility = json.loads(view.stdout).get("visibility")
        if visibility != "PRIVATE":
            raise RuntimeError(f"Vault repo must be private, got {visibility}: {config.repo}")
        return
    if not create:
        raise CommandError(view)
    run(
        [
            "gh",
            "repo",
            "create",
            config.repo,
            "--private",
            "--description",
            "Private Codex Sync Kit vault",
        ]
    )


def ensure_clone(config: AppConfig) -> Path:
    require_tools()
    vault_dir = config.resolved_vault_dir
    vault_dir.parent.mkdir(parents=True, exist_ok=True)
    if (vault_dir / ".git").exists():
        ensure_vault_remote_matches(vault_dir, config)
        run(["git", "fetch", "--prune"], cwd=vault_dir)
        run(["git", "pull", "--ff-only"], cwd=vault_dir, check=False)
        return vault_dir

    if vault_dir.exists() and any(vault_dir.iterdir()):
        raise RuntimeError(f"Vault directory exists but is not a git repo: {vault_dir}")
    if vault_dir.exists():
        vault_dir.rmdir()
    run(["gh", "repo", "clone", config.repo, str(vault_dir)])
    ensure_vault_remote_matches(vault_dir, config)
    return vault_dir


def ensure_vault_remote_matches(vault_dir: Path, config: AppConfig) -> None:
    view = run(["gh", "repo", "view", "--json", "nameWithOwner"], cwd=vault_dir, check=False)
    if view.returncode != 0:
        raise CommandError(view)
    actual = json.loads(view.stdout).get("nameWithOwner")
    if actual != config.repo:
        raise RuntimeError(
            f"Vault directory points at {actual}, expected {config.repo}: {vault_dir}"
        )


def commit_and_push(vault_dir: Path, message: str) -> bool:
    run(["git", "add", "-A"], cwd=vault_dir)
    status = run(["git", "status", "--porcelain"], cwd=vault_dir)
    if not status.stdout.strip():
        return False
    ensure_local_git_identity(vault_dir)
    run(["git", "commit", "-m", message], cwd=vault_dir)
    upstream = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=vault_dir,
        check=False,
    )
    if upstream.returncode == 0 and upstream.stdout.strip():
        run(["git", "push"], cwd=vault_dir)
    else:
        run(["git", "push", "-u", "origin", "HEAD:main"], cwd=vault_dir)
    return True


def init_vault_repo_if_empty(vault_dir: Path) -> None:
    head = run(["git", "rev-parse", "--verify", "HEAD"], cwd=vault_dir, check=False)
    if head.returncode != 0:
        run(["git", "checkout", "-B", "main"], cwd=vault_dir)
    readme = vault_dir / "README.md"
    gitignore = vault_dir / ".gitignore"
    if not readme.exists():
        readme.write_text(
            "# Codex Sync Vault\n\nPrivate snapshots created by Codex Sync Kit.\n",
            encoding="utf-8",
        )
    if not gitignore.exists():
        gitignore.write_text(".DS_Store\nThumbs.db\n", encoding="utf-8")


def ensure_local_git_identity(repo_dir: Path) -> None:
    current_email = run(["git", "config", "user.email"], cwd=repo_dir, check=False)
    if current_email.returncode == 0 and current_email.stdout.strip():
        return

    user_id = run(["gh", "api", "user", "--jq", ".id"], check=False).stdout.strip()
    login = run(["gh", "api", "user", "--jq", ".login"], check=False).stdout.strip()
    if user_id and login:
        name = login
        email = f"{user_id}+{login}@users.noreply.github.com"
    else:
        name = "Codex Sync Kit"
        email = "codex-sync-kit@users.noreply.github.com"
    run(["git", "config", "user.name", name], cwd=repo_dir)
    run(["git", "config", "user.email", email], cwd=repo_dir)
