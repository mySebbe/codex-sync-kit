# Architecture

Codex Sync Kit has three pieces:

- Python CLI: scans `.codex`, creates snapshots, restores files, and drives GitHub through `git` and `gh`.
- Private vault: a GitHub repository containing timestamped `snapshots/<id>/files` plus `manifest.json`.
- Codex plugin: a skill that tells Codex how to use the CLI safely.

The CLI is intentionally dependency-light. The first release avoids direct GitHub API libraries and uses the already common `gh` CLI.
