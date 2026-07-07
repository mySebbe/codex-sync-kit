from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath

SAFE_PATTERNS = (
    "AGENTS.md",
    "config.toml",
    "skills/**",
    "rules/**",
    "plugins/**/plugin.json",
    "plugins/**/marketplace.json",
    "tools/**/*.md",
    "tools/**/*.json",
    "tools/**/*.toml",
    "tools/**/*.py",
)

BLOCKED_PATTERNS = (
    "auth.json",
    "cap_sid",
    ".sandbox-secrets/**",
    "**/.env",
    "**/*.pem",
    "**/*.key",
    "**/*token*",
    "**/*secret*",
    "**/*password*",
    "**/*.sqlite",
    "**/*.sqlite-shm",
    "**/*.sqlite-wal",
    "**/*.db",
    "**/*.db-shm",
    "**/*.db-wal",
    "logs_*.sqlite*",
    "goals_*.sqlite*",
    "state_*.sqlite*",
    "memories_*.sqlite*",
)

NOISY_PATTERNS = (
    ".tmp/**",
    "tmp/**",
    "cache/**",
    "log/**",
    "sessions/**",
    "archived_sessions/**",
    "node_repl/**",
    "process_manager/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
)

RISKY_PATTERNS = (
    "config.toml",
    "tools/**",
    ".codex-global-state*.json*",
    "chrome-native-hosts*.json",
)


@dataclass(frozen=True)
class Classification:
    relative_path: str
    allowed: bool
    risky: bool
    reason: str


def classify(
    relative_path: str,
    profile: str = "safe",
    *,
    include_risky: bool = False,
) -> Classification:
    normalized = _norm(relative_path)
    if _matches(normalized, BLOCKED_PATTERNS):
        return Classification(normalized, False, True, "blocked-secret-or-live-state")
    if _matches(normalized, NOISY_PATTERNS):
        return Classification(normalized, False, False, "excluded-noisy-runtime-state")

    risky = _matches(normalized, RISKY_PATTERNS)
    if profile == "safe":
        allowed = _matches(normalized, SAFE_PATTERNS) and (
            include_risky or not risky or normalized == "config.toml"
        )
        reason = "safe-profile" if allowed else "not-in-safe-profile"
        return Classification(normalized, allowed, risky, reason)

    if profile == "full":
        allowed = include_risky or not risky
        reason = "full-profile" if allowed else "risky-needs-confirmation"
        return Classification(normalized, allowed, risky, reason)

    if profile == "custom":
        allowed = include_risky or not risky
        reason = "custom-profile" if allowed else "risky-needs-confirmation"
        return Classification(normalized, allowed, risky, reason)

    raise ValueError(f"Unknown profile: {profile}")


def matches_any(relative_path: str, patterns: tuple[str, ...]) -> bool:
    return _matches(_norm(relative_path), patterns)


def _matches(relative_path: str, patterns: tuple[str, ...]) -> bool:
    return any(_match(relative_path, pattern) for pattern in patterns)


def _match(relative_path: str, pattern: str) -> bool:
    if fnmatch(relative_path, pattern):
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return relative_path == prefix or relative_path.startswith(prefix + "/")
    return PurePosixPath(relative_path).match(pattern)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")
