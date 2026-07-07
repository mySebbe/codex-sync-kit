from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import default_config_path, default_vault_dir


@dataclass(frozen=True)
class AppConfig:
    provider: str = "github"
    owner: str = "mySebbe"
    vault: str = "codex-sync-vault"
    codex_home: str | None = None
    vault_dir: str | None = None
    custom_include: tuple[str, ...] = field(default_factory=tuple)
    custom_exclude: tuple[str, ...] = field(default_factory=tuple)

    @property
    def repo(self) -> str:
        return f"{self.owner}/{self.vault}"

    @property
    def resolved_vault_dir(self) -> Path:
        if self.vault_dir:
            return Path(self.vault_dir).expanduser()
        return default_vault_dir()


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or default_config_path()
    if not config_path.exists():
        return AppConfig()

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    github = data.get("github", {})
    sync = data.get("sync", {})
    return AppConfig(
        provider=str(data.get("provider", "github")),
        owner=str(github.get("owner", "mySebbe")),
        vault=str(github.get("vault", "codex-sync-vault")),
        codex_home=_optional_str(sync.get("codex_home")),
        vault_dir=_optional_str(sync.get("vault_dir")),
        custom_include=tuple(str(item) for item in sync.get("custom_include", [])),
        custom_exclude=tuple(str(item) for item in sync.get("custom_exclude", [])),
    )


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        [
            'provider = "github"',
            "",
            "[github]",
            f'owner = "{_escape(config.owner)}"',
            f'vault = "{_escape(config.vault)}"',
            "",
            "[sync]",
            f'codex_home = "{_escape(config.codex_home or "")}"',
            f'vault_dir = "{_escape(str(config.resolved_vault_dir))}"',
            f"custom_include = {_toml_string_array(config.custom_include)}",
            f"custom_exclude = {_toml_string_array(config.custom_exclude)}",
            "",
        ]
    )
    config_path.write_text(body, encoding="utf-8")
    return config_path


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _toml_string_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(f'"{_escape(value)}"' for value in values) + "]"


_BARE_TOML_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SECRET_RE = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|bearer|authorization|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(Bearer\s+\S+|sk-[A-Za-z0-9_-]+|gh[opsu]_[A-Za-z0-9_]+|xox[baprs]-\S+)",
    re.IGNORECASE,
)


def redact_config_text(text: str) -> str:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return _redact_config_lines(text)
    redacted = _redact_toml_value("", data)
    if isinstance(redacted, dict):
        return _dump_toml(redacted)
    return ""


def _redact_config_lines(text: str) -> str:
    redacted: list[str] = []
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line else line
        if "=" in line and (_SECRET_RE.search(key) or _SECRET_VALUE_RE.search(line)):
            redacted.append(f"{key} = \"<redacted>\"")
        else:
            redacted.append(line)
    return "\n".join(redacted) + ("\n" if text.endswith("\n") else "")


def _redact_toml_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(child_key): _redact_toml_value(str(child_key), child)
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        if _SECRET_RE.search(key):
            return "<redacted>"
        return [_redact_toml_value(key, item) for item in value]
    if _SECRET_RE.search(key):
        return "<redacted>"
    if isinstance(value, str) and _SECRET_VALUE_RE.search(value):
        return "<redacted>"
    return value


def _dump_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    scalar_items = {key: value for key, value in data.items() if not isinstance(value, dict)}
    section_items = {key: value for key, value in data.items() if isinstance(value, dict)}
    for key, value in scalar_items.items():
        lines.append(f"{_format_toml_key(key)} = {_format_toml_value(value)}")
    for key, value in section_items.items():
        if lines:
            lines.append("")
        _dump_toml_section(lines, [key], value)
    return "\n".join(lines) + "\n"


def _dump_toml_section(lines: list[str], prefix: list[str], data: dict[str, Any]) -> None:
    lines.append(f"[{'.'.join(_format_toml_key(part) for part in prefix)}]")
    nested: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            nested[key] = value
        else:
            lines.append(f"{_format_toml_key(key)} = {_format_toml_value(value)}")
    for key, value in nested.items():
        lines.append("")
        _dump_toml_section(lines, [*prefix, key], value)


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    return f'"{_escape(str(value))}"'


def _format_toml_key(key: str) -> str:
    if _BARE_TOML_KEY_RE.match(key):
        return key
    return f'"{_escape(key)}"'
