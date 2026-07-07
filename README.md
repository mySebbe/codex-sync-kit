# Codex Sync Kit

Codex Sync Kit is a Windows-first open-source helper for keeping a Codex setup portable across fresh installs. It syncs selected `.codex` configuration into a private GitHub vault so a new machine can restore the useful parts instead of starting from scratch.

The first release focuses on GitHub private repositories. OneDrive and folder backends are intentionally left as future adapters.

## 1-Click Install

```powershell
irm https://raw.githubusercontent.com/mySebbe/codex-sync-kit/main/install.ps1 | iex
```

The installer creates a local Python virtual environment, installs `codex-sync-kit`, installs the Codex plugin source, and registers the plugin with Codex.

## Quick Start

```powershell
codex-sync init --provider github --owner mySebbe --vault codex-sync-vault
codex-sync scan --profile safe
codex-sync push --profile safe
codex-sync pull --dry-run
codex-sync restore
```

Use `--profile full --include-risky --confirm-risky "SYNC RISKY CODEX FILES"` only when you intentionally want to include risky local files. Auth files, live SQLite databases, WAL/SHM files, caches, logs, and obvious secret files stay blocked.

## Profiles

- `safe`: `AGENTS.md`, sanitized `config.toml`, skills, rules, selected plugin metadata, and small tool manifests/scripts.
- `full`: broad `.codex` coverage, but risky files require explicit confirmation and blocked files still stay out.
- `custom`: include/exclude globs stored in `%APPDATA%\codex-sync-kit\config.toml`.

## Codex Plugin

The repo includes `plugin/codex-sync-kit`, a Codex plugin with a `codex-sync` skill. After install, use prompts like:

```text
Use $codex-sync to scan my Codex setup.
```

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e . pytest ruff build
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m build --sdist --wheel
```
