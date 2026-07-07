from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "codex-sync-kit"


def home_dir() -> Path:
    return Path.home()


def default_codex_home() -> Path:
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return home_dir() / ".codex"


def app_data_dir() -> Path:
    root = os.environ.get("APPDATA")
    if root:
        return Path(root) / APP_NAME
    return home_dir() / ".config" / APP_NAME


def local_app_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / APP_NAME
    return home_dir() / ".local" / "share" / APP_NAME


def default_config_path() -> Path:
    return app_data_dir() / "config.toml"


def default_vault_dir() -> Path:
    return local_app_dir() / "vault"


def normalize_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
