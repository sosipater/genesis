# Logging and Diagnostics

## Logging Policy

- structured JSON logs (desktop + mobile)
- subsystem field required (`ui`, `sync`, `db`, `timers`, `packaging`, `startup`)
- human-readable message plus machine-parseable metadata

## Required Log Metadata

- timestamp UTC
- level
- subsystem
- device_id
- session_id (if available)
- correlation_id/request_id (sync operations)

## Desktop Diagnostics

- file logs with daily rotation
- sync history view
- startup config snapshot (redacted sensitive values)
- `/health` endpoint status summary
- `/sync/status` exposes queue counts and last sync timestamps
- `tools/ops_desktop.py diagnostics` prints version/path/data/media health summary
- `tools/ops_desktop.py media-scan` reports orphans, missing files, and dangling references

## Mobile Diagnostics

- in-app diagnostics panel with:
  - last sync result
  - last successful sync timestamp
  - host endpoint currently configured
  - queued change count
  - app/schema/protocol/share-format version visibility

## Backup and Recovery Diagnostics

- `tools/ops_desktop.py backup --out <path.zip>` creates a backup archive.
- `tools/ops_desktop.py validate-backup --path <path.zip>` validates manifest, checksums, and required payload.
- `tools/ops_desktop.py restore --path <path.zip> --allow-replace` performs explicit full-replace restore.
- restore will fail with a clear message when the database file is locked by a running app instance.

## Release Readiness Report

Single-command pre-release confidence check:

- `tools/release_readiness_report.py`
- optional flags:
  - `--with-backup`: create/validate temporary backup artifact
  - `--with-tests`: run desktop tests during report
  - `--verbose`: include detailed media ID lists for failed/warned media checks

Output contract:

- each check prints `PASS` / `WARN` / `FAIL`
- checks are grouped by category (versioning/data/media/backup/paths/tests)
- summary includes overall status and recommended actions

Interpretation:

- release blocker: any `FAIL`
- acceptable with caution: `WARN` only
- high confidence: all `PASS` (or expected optional warnings)

## Version Reporting

Desktop diagnostics report now includes:

- app id/version
- local schema version
- sync protocol version
- recipe share format version

## Desktop App-Data Directory Rules

Default desktop app-data root is `%APPDATA%\Genesis` for new installs (legacy: `%APPDATA%\RecipeForge`). Override via `GENESIS_DATA_DIR` (or legacy `RECIPE_FORGE_DATA_DIR`):

- `data/genesis.db`: SQLite source of truth (legacy filename: `recipe_forge.db`)
- `media/`: managed media binaries
- `logs/`: structured log files
- `backups/`: recommended backup output location
- `temp/`: restore/temp operations
- `config/preferences.json`: local app continuity preferences

## Crash and Error Handling

- unhandled exceptions logged with stack traces
- sync errors persisted with entity-level detail
- failures never silently swallowed
- user-visible safe error summaries for actionable recovery

