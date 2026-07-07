# Security Policy

Codex Sync Kit is designed to avoid syncing secrets by default.

## Default protections

- `auth.json`, sandbox secrets, token-like files, private keys, live SQLite databases, WAL/SHM files, logs, caches, and sessions are blocked or excluded.
- `config.toml` is copied with secret-looking keys redacted.
- Risky categories require the exact confirmation phrase `SYNC RISKY CODEX FILES`.
- The default vault is a private GitHub repository.

## Reporting

Please open a private security advisory on GitHub or email the maintainer listed on the GitHub profile.
