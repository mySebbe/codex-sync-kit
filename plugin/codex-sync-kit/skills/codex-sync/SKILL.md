---
name: codex-sync
description: Use when the user wants to sync, back up, inspect, or restore their local Codex setup with Codex Sync Kit, especially on Windows with a private GitHub vault. Supports safe, full, and custom profile workflows through the `codex-sync` CLI.
---

# Codex Sync

Use the local `codex-sync` CLI. Prefer `safe` until the user explicitly asks for broader coverage. Review scan output before push or restore actions.

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
codex-sync scan --profile safe
codex-sync push --profile safe
```

Inspect available snapshots:

```powershell
codex-sync pull --dry-run
```

Verify the latest snapshot's inventory and SHA-256 hashes before restore:

```powershell
codex-sync verify --snapshot latest --require-hashes
```

Restore without copying first:

```powershell
codex-sync restore
```

Restore for real only after the dry-run output is reviewed and the user explicitly asks to apply it:

```powershell
codex-sync restore --apply
```

Legacy v1 snapshots have no per-file hashes and are rejected by default. Use
`--allow-legacy-unhashed` only when the user explicitly accepts that risk after reviewing the
snapshot and vault history.

## Risky full sync

Only use this when the user explicitly asks to include risky files:

```powershell
codex-sync push --profile full --include-risky --confirm-risky "SYNC RISKY CODEX FILES"
```

Never bypass blocked auth, live database, cache, log, or session exclusions.
