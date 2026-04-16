# Recipe Forge

**Repository**: [github.com/sosipater/genesis](https://github.com/sosipater/genesis)

Recipe Forge is a dual-app, offline-first system for structured recipe authoring and guided cooking:

- **Desktop (Windows 11, Python + PySide6)**: primary authoring environment, local sync host, content packaging/export toolchain.
- **Mobile (Android, Flutter)**: primary cooking/runtime environment, LAN sync client, practical editing support.

The project is built around durable foundations:

- versioned schemas
- explicit content scope separation (bundled vs local)
- modular architecture boundaries
- safe sync behavior with inspectable logs

## Repository Map

- `CONTEXT.md`: high-signal engineering overview for contributors and AI agents (stack, phases, sync entities, refinement work).
- `docs/`: product + architecture + data + sync + roadmap decisions.
- `shared/`: versioned contracts and schema assets used across desktop/mobile/tools.
- `bundled_content/`: app-shipped content package + manifest.
- `tools/`: validation, export, seed, and sync diagnostics scripts.
- `desktop/`: desktop app source, tests, scripts.
- `mobile/`: Flutter app project.
- `tests/`: cross-app integration and contract tests.

## Initial Priorities

1. Lock schema and persistence foundations.
2. Implement desktop storage + sync host.
3. Implement mobile storage + sync client.
4. Build authoring UX (desktop) and cooking UX (mobile) on stable contracts.

## PowerShell Shortcuts

From the repository root:

- `.\mobile.ps1 get`
- `.\mobile.ps1 run`
- `.\mobile.ps1 test`
- `.\mobile.ps1 analyze`
- `.\mobile.ps1 check`
- `.\desktop.ps1 run`
- `.\desktop.ps1 sync-host`
- `.\desktop.ps1 test`
- `.\desktop.ps1 diagnostics`
- `.\desktop.ps1 media-scan`
- `.\desktop.ps1 release-check`
- `.\desktop.ps1 release-check -WithBackup -WithTests -VerboseReport`
- `.\desktop.ps1 backup .\backup\recipe_forge_backup.zip`
- `.\desktop.ps1 validate-backup .\backup\recipe_forge_backup.zip`
- `.\desktop.ps1 restore .\backup\recipe_forge_backup.zip -AllowReplace`

## Desktop Operational Data

Desktop runtime data defaults to:

- `%APPDATA%\RecipeForge\data\recipe_forge.db`
- `%APPDATA%\RecipeForge\media\...`
- `%APPDATA%\RecipeForge\logs\...`
- `%APPDATA%\RecipeForge\backups\...`
- `%APPDATA%\RecipeForge\config\preferences.json`

Override base path with `RECIPE_FORGE_DATA_DIR`.

## Packaging and Install (Practical Baseline)

Desktop (Windows, small-group distribution):

1. Install Python 3.12+.
2. Install dependencies from repo environment.
3. Run `.\desktop.ps1 run` for authoring app and `.\desktop.ps1 sync-host` when host mode is needed.
4. Use backup/restore/diagnostics commands above for operational safety.

## Release Readiness Report

Run before sharing builds with real users:

- `python tools/release_readiness_report.py`
- `python tools/release_readiness_report.py --with-backup`
- `python tools/release_readiness_report.py --with-backup --with-tests --verbose`
- `.\desktop.ps1 release-check -WithBackup -WithTests -VerboseReport`

Report states:

- `PASS`: healthy check
- `WARN`: non-blocking issue or skipped optional check
- `FAIL`: blocking issue to fix before release

Mobile (Android):

1. `.\mobile.ps1 get`
2. `.\mobile.ps1 run` (debug deploy) or standard `flutter build apk`.
3. Notifications require runtime notification permission (platform prompt).
4. Media path import currently expects file paths provided by user workflow.

## Clone and first-time setup

1. Clone: `git clone https://github.com/sosipater/genesis.git` (or SSH equivalent).
2. **Desktop**: Python 3.12+. From the repo root: `pip install -e ".[dev]"` (see `pyproject.toml` for runtime + pytest deps).
3. **Mobile**: `cd mobile/recipe_forge_mobile` and run `flutter pub get` (regenerates local `.dart_tool/`; not committed).
4. Run tests: `.\desktop.ps1 test` and `.\mobile.ps1 test` from repo root when scripts exist.

Do not commit `.pytest_cache/`, `__pycache__/`, or `.dart_tool/`; they are listed in the root `.gitignore`.

