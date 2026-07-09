# Security Review - July 2026

## Scope

The review covered snapshot creation, manifest parsing, restore boundaries, Git invocation,
configuration redaction, the Windows installer, and GitHub workflow configuration.

## Fixed Findings

1. **Snapshot contents were not integrity checked.** Manifest schema v2 now records the copied
   size and SHA-256 digest of every file. `codex-sync verify` and restore validate those values.
2. **A snapshot directory could contain unlisted files.** Verification now requires an exact match
   between the manifest inventory and regular files below `files/`.
3. **Snapshot identifiers were not independently bounded.** Verification rejects absolute paths,
   parent traversal, multi-component identifiers, and paths escaping the vault snapshot root.
4. **Manifest parsing had no explicit resource limits.** Verification caps the manifest at 10 MiB
   and 20,000 entries, and caps actual/declared snapshot content at 1 GiB.
5. **Vault junctions and linked marker/files could cross trust boundaries.** Snapshot roots,
   manifests, files, and `LATEST` now reject symlinks, junctions/reparse points, and hard links.
6. **Legacy snapshots were restored without an explicit risk decision.** Restore now requires
   schema-v2 hashes unless `--allow-legacy-unhashed` is explicitly supplied.

## Existing Controls Revalidated

- Restore rejects blocked paths, source symlinks, destination symlinks, hard links, and escapes.
- Configuration redaction covers common token/PAT/password/client-secret forms.
- Git commands use argument arrays with `shell=False` and push explicitly to `origin/main`.
- The installer defaults to an immutable release tag and supports SHA-256 verification.

## Residual Risk

SHA-256 entries detect accidental corruption and file-only tampering, but the manifest is not
cryptographically signed. An attacker who can rewrite both a private vault commit and every hash
can create a self-consistent malicious snapshot. GitHub account security, protected credentials,
and review of unexpected vault history remain required trust controls.

## Validation

The final PR gate runs Pytest, Ruff, Bandit, pip-audit, build, and Trivy filesystem scanning. Exact
results are recorded in the pull request after the final clean-tree run.
