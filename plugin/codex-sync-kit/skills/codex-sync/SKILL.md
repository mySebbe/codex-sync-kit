---
name: codex-sync
description: Use when the user wants to sync, back up, inspect, or restore their local Codex setup with Codex Sync Kit, especially on Windows with a private GitHub vault. Supports safe, full, and custom profile workflows through the `codex-sync` CLI.
---

# Codex Sync

Use the local `codex-sync` CLI. Prefer `safe` until the user explicitly asks for broader coverage.

## Common flows

Scan:

```powershell
codex-sync scan --profile safe
```

Initialize the default private GitHub vault:

```powershell
codex-sync init --provider github --owner mySebbe --vault codex-sync-vault
```

Push a safe snapshot:

```powershell
codex-sync push --profile safe
```

Inspect available snapshots:

```powershell
codex-sync pull --dry-run
```

Restore without copying first:

```powershell
codex-sync restore
```

Restore for real:

```powershell
codex-sync restore --apply
```

## Risky full sync

Only use this when the user explicitly asks to include risky files:

```powershell
codex-sync push --profile full --include-risky --confirm-risky "SYNC RISKY CODEX FILES"
```

Never bypass blocked auth, live database, cache, log, or session exclusions.
