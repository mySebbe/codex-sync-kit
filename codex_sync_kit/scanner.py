from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .paths import default_codex_home, normalize_relative
from .rules import classify, matches_any


@dataclass(frozen=True)
class ScanItem:
    relative_path: str
    absolute_path: Path
    size: int
    allowed: bool
    risky: bool
    reason: str


def resolve_codex_home(config: AppConfig | None = None, explicit: Path | None = None) -> Path:
    if explicit:
        return explicit.expanduser()
    if config and config.codex_home:
        return Path(config.codex_home).expanduser()
    return default_codex_home()


def scan(
    codex_home: Path,
    *,
    profile: str,
    include_risky: bool = False,
    custom_include: tuple[str, ...] = (),
    custom_exclude: tuple[str, ...] = (),
) -> list[ScanItem]:
    if not codex_home.exists():
        raise FileNotFoundError(f"Codex home does not exist: {codex_home}")

    items: list[ScanItem] = []
    for path in sorted(codex_home.rglob("*")):
        if not path.is_file():
            continue
        rel = normalize_relative(path, codex_home)
        item_profile = profile
        classification = classify(rel, item_profile, include_risky=include_risky)
        allowed = classification.allowed
        reason = classification.reason
        if profile == "custom":
            if custom_include:
                allowed = matches_any(rel, custom_include)
                reason = "custom-include" if allowed else "not-in-custom-include"
            if allowed and custom_exclude and matches_any(rel, custom_exclude):
                allowed = False
                reason = "custom-exclude"
            if allowed:
                recheck = classify(rel, "full", include_risky=include_risky)
                allowed = recheck.allowed
                reason = reason if allowed else recheck.reason
                classification = recheck

        items.append(
            ScanItem(
                relative_path=rel,
                absolute_path=path,
                size=path.stat().st_size,
                allowed=allowed,
                risky=classification.risky,
                reason=reason,
            )
        )
    return items


def selected_items(items: list[ScanItem]) -> list[ScanItem]:
    return [item for item in items if item.allowed]


def summarize(items: list[ScanItem]) -> dict[str, int]:
    selected = selected_items(items)
    return {
        "files_seen": len(items),
        "files_selected": len(selected),
        "bytes_selected": sum(item.size for item in selected),
        "risky_seen": sum(1 for item in items if item.risky),
        "blocked_or_excluded": sum(1 for item in items if not item.allowed),
    }
