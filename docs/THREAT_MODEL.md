# Threat Model

Primary risks:

- Accidentally committing credentials.
- Restoring stale or machine-bound runtime state.
- Confusing a public tool repo with a private vault repo.

Mitigations:

- Block known auth, secret, live database, log, cache, and session patterns.
- Redact secret-looking `config.toml` keys.
- Create vault repositories as private by default.
- Keep the tool repo and vault repo separate.
