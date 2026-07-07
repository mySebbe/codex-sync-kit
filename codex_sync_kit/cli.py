from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import AppConfig, load_config, save_config
from .git_backend import (
    commit_and_push,
    ensure_clone,
    ensure_private_repo,
    init_vault_repo_if_empty,
)
from .paths import default_codex_home, home_dir
from .restore import restore_snapshot
from .scanner import resolve_codex_home, scan, selected_items, summarize
from .snapshot import create_snapshot, latest_snapshot, list_snapshots

RISK_CONFIRMATION = "SYNC RISKY CODEX FILES"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-sync",
        description="Sync Codex setup to a private vault.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create local config and optional private GitHub vault.")
    init.add_argument("--provider", default="github", choices=["github"])
    init.add_argument("--owner", default="mySebbe")
    init.add_argument("--vault", default="codex-sync-vault")
    init.add_argument("--codex-home", type=Path, default=None)
    init.add_argument("--vault-dir", type=Path, default=None)
    init.add_argument("--no-create", action="store_true", help="Do not create the private repo.")

    scan_cmd = sub.add_parser("scan", help="Show selected and excluded Codex files.")
    add_profile_args(scan_cmd)
    scan_cmd.add_argument("--json", action="store_true", help="Print machine-readable scan output.")

    push = sub.add_parser("push", help="Create and push a snapshot.")
    add_profile_args(push)

    pull = sub.add_parser("pull", help="Fetch vault and list available snapshots.")
    pull.add_argument("--dry-run", action="store_true")

    restore = sub.add_parser("restore", help="Restore a snapshot into CODEX_HOME.")
    restore.add_argument("--snapshot", default=None)
    restore.add_argument("--apply", action="store_true", help="Actually copy files.")
    restore.add_argument("--codex-home", type=Path, default=None)

    plugin = sub.add_parser("plugin", help="Codex plugin helpers.")
    plugin_sub = plugin.add_subparsers(dest="plugin_command", required=True)
    install = plugin_sub.add_parser("install", help="Install the bundled Codex plugin locally.")
    install.add_argument("--source", type=Path, default=None)
    install.add_argument("--target-root", type=Path, default=home_dir() / "plugins")
    install.add_argument(
        "--marketplace",
        type=Path,
        default=home_dir() / ".agents" / "plugins" / "marketplace.json",
    )

    return parser


def add_profile_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", choices=["safe", "full", "custom"], default="safe")
    parser.add_argument("--codex-home", type=Path, default=None)
    parser.add_argument("--include-risky", action="store_true")
    parser.add_argument("--confirm-risky", default="")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return cmd_init(args)
        if args.command == "scan":
            return cmd_scan(args)
        if args.command == "push":
            return cmd_push(args)
        if args.command == "pull":
            return cmd_pull(args)
        if args.command == "restore":
            return cmd_restore(args)
        if args.command == "plugin":
            return cmd_plugin(args)
    except Exception as exc:  # noqa: BLE001 - CLI should show concise failures.
        print(f"codex-sync: error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    config = AppConfig(
        provider=args.provider,
        owner=args.owner,
        vault=args.vault,
        codex_home=str(args.codex_home or default_codex_home()),
        vault_dir=str(args.vault_dir) if args.vault_dir else None,
    )
    if config.provider == "github":
        ensure_private_repo(config, create=not args.no_create)
    path = save_config(config)
    print(f"Wrote config: {path}")
    print(f"Vault repo: {config.repo}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    config = load_config()
    items = _scan_from_args(args, config)
    if args.json:
        print(
            json.dumps(
                {
                    "summary": summarize(items),
                    "items": [
                        {
                            "path": item.relative_path,
                            "size": item.size,
                            "selected": item.allowed,
                            "risky": item.risky,
                            "reason": item.reason,
                        }
                        for item in items
                    ],
                },
                indent=2,
            )
        )
    else:
        summary = summarize(items)
        print(
            f"Seen {summary['files_seen']} files, selected {summary['files_selected']} "
            f"({summary['bytes_selected']} bytes)."
        )
        for item in items:
            marker = "+" if item.allowed else "-"
            risk = " risky" if item.risky else ""
            print(f"{marker} {item.relative_path} [{item.reason}{risk}]")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    config = load_config()
    items = selected_items(_scan_from_args(args, config))
    if not items:
        raise RuntimeError("No files selected for snapshot.")
    ensure_private_repo(config, create=True)
    vault = ensure_clone(config)
    init_vault_repo_if_empty(vault)
    codex_home = resolve_codex_home(config, args.codex_home)
    snapshot_root = create_snapshot(
        vault_root=vault,
        codex_home=codex_home,
        items=items,
        profile=args.profile,
        include_risky=args.include_risky,
    )
    changed = commit_and_push(vault, f"Add Codex snapshot {snapshot_root.name}")
    print(f"Snapshot: {snapshot_root.name}")
    print("Pushed changes." if changed else "No vault changes to push.")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    config = load_config()
    vault = ensure_clone(config)
    snapshots = list_snapshots(vault)
    print(f"Vault: {vault}")
    print(f"Snapshots: {len(snapshots)}")
    for item in snapshots:
        print(item)
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    config = load_config()
    vault = ensure_clone(config)
    snapshot = args.snapshot or latest_snapshot(vault)
    if not snapshot:
        raise RuntimeError("No snapshot available.")
    codex_home = resolve_codex_home(config, args.codex_home)
    planned = restore_snapshot(
        vault_root=vault,
        snapshot=snapshot,
        codex_home=codex_home,
        apply=args.apply,
    )
    mode = "Restored" if args.apply else "Dry-run restore"
    print(f"{mode} {len(planned)} files from {snapshot}.")
    for path in planned:
        print(path)
    if not args.apply:
        print("Pass --apply to copy files.")
    return 0


def cmd_plugin(args: argparse.Namespace) -> int:
    if args.plugin_command != "install":
        raise RuntimeError(f"Unknown plugin command: {args.plugin_command}")
    source = args.source or _default_plugin_source()
    target = args.target_root / "codex-sync-kit"
    if not source.exists():
        raise FileNotFoundError(f"Plugin source not found: {source}")
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    _write_marketplace(args.marketplace)
    print(f"Installed plugin source: {target}")
    print(f"Marketplace: {args.marketplace}")
    print("Run: codex plugin add codex-sync-kit@personal")
    return 0


def _scan_from_args(args: argparse.Namespace, config: AppConfig):
    if args.include_risky and args.confirm_risky != RISK_CONFIRMATION:
        raise RuntimeError(f'Risky files require --confirm-risky "{RISK_CONFIRMATION}"')
    codex_home = resolve_codex_home(config, args.codex_home)
    return scan(
        codex_home,
        profile=args.profile,
        include_risky=args.include_risky,
        custom_include=config.custom_include,
        custom_exclude=config.custom_exclude,
    )


def _default_plugin_source() -> Path:
    cwd_source = Path.cwd() / "plugin" / "codex-sync-kit"
    if cwd_source.exists():
        return cwd_source
    return Path(__file__).resolve().parents[1] / "plugin" / "codex-sync-kit"


def _write_marketplace(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "name": "codex-sync-kit",
        "source": {"source": "local", "path": "./plugins/codex-sync-kit"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}
    plugins = [
        plugin for plugin in data.get("plugins", []) if plugin.get("name") != "codex-sync-kit"
    ]
    plugins.append(entry)
    data["plugins"] = plugins
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
