"""Pre-release operational readiness report (non-destructive by default)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.runtime_paths import RuntimePaths, build_runtime_paths
from desktop.app.services.backup_service import BackupService
from desktop.app.services.media_service import MediaService
from desktop.app.versioning import APP_VERSION, RECIPE_SHARE_FORMAT_VERSION, SYNC_PROTOCOL_VERSION


@dataclass(slots=True)
class CheckResult:
    category: str
    label: str
    status: str  # PASS|WARN|FAIL
    detail: str


def _status_prefix(status: str) -> str:
    return f"[{status}]"


def _line(result: CheckResult) -> str:
    return f"{_status_prefix(result.status)} {result.label} - {result.detail}"


def _summarize(results: list[CheckResult]) -> tuple[str, list[str]]:
    fail_count = sum(1 for result in results if result.status == "FAIL")
    warn_count = sum(1 for result in results if result.status == "WARN")
    if fail_count:
        overall = "FAIL"
    elif warn_count:
        overall = "WARN"
    else:
        overall = "PASS"
    actions: list[str] = []
    for result in results:
        if result.status in {"WARN", "FAIL"}:
            actions.append(f"{result.label}: {result.detail}")
    return overall, actions


def run_readiness_checks(
    *,
    project_root: Path,
    with_backup: bool,
    with_tests: bool,
    verbose: bool,
    runtime_paths: RuntimePaths | None = None,
) -> tuple[list[CheckResult], str, list[str]]:
    paths = runtime_paths or build_runtime_paths(project_root)
    results: list[CheckResult] = []
    database: Database | None = None
    try:
        try:
            database = Database(paths.db_path)
            repository = RecipeRepository(database.conn)
            results.append(CheckResult("data", "Database accessible", "PASS", str(paths.db_path)))
        except Exception as exc:
            results.append(CheckResult("data", "Database accessible", "FAIL", str(exc)))
            overall, actions = _summarize(results)
            return results, overall, actions

        # Versioning
        results.append(CheckResult("versioning", "App version", "PASS", APP_VERSION))
        results.append(CheckResult("versioning", "Schema version", "PASS", str(database.schema_version)))
        results.append(CheckResult("versioning", "Sync protocol version", "PASS", str(SYNC_PROTOCOL_VERSION)))
        results.append(CheckResult("versioning", "Share format version", "PASS", str(RECIPE_SHARE_FORMAT_VERSION)))

        # Data health
        integrity = database.conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity == "ok":
            results.append(CheckResult("data", "SQLite integrity", "PASS", "PRAGMA integrity_check ok"))
        else:
            results.append(CheckResult("data", "SQLite integrity", "FAIL", str(integrity)))
        recipes = repository.list_recipes(include_deleted=False)
        steps = sum(len(recipe.steps) for recipe in recipes)
        ingredients = sum(len(recipe.ingredients) for recipe in recipes)
        equipment = sum(len(recipe.equipment) for recipe in recipes)
        results.append(
            CheckResult(
                "data",
                "Data counts",
                "PASS",
                f"recipes={len(recipes)} steps={steps} ingredients={ingredients} equipment={equipment}",
            )
        )

        # Media health
        media_service = MediaService(repository, paths.media_root)
        media_report = media_service.scan_health()
        orphan_count = len(media_report["orphan_assets"])
        missing_count = len(media_report["missing_files"])
        dangling_count = len(media_report["dangling_references"])
        results.append(
            CheckResult(
                "media",
                "Media orphan assets",
                "WARN" if orphan_count else "PASS",
                str(orphan_count),
            )
        )
        results.append(
            CheckResult(
                "media",
                "Media missing files",
                "FAIL" if missing_count else "PASS",
                str(missing_count),
            )
        )
        results.append(
            CheckResult(
                "media",
                "Media dangling references",
                "FAIL" if dangling_count else "PASS",
                str(dangling_count),
            )
        )
        if verbose and (orphan_count or missing_count or dangling_count):
            if orphan_count:
                results.append(CheckResult("media", "Orphan media ids", "WARN", ", ".join(media_report["orphan_assets"])))
            if missing_count:
                results.append(CheckResult("media", "Missing media ids", "FAIL", ", ".join(media_report["missing_files"])))
            if dangling_count:
                results.append(
                    CheckResult("media", "Dangling reference ids", "FAIL", ", ".join(media_report["dangling_references"]))
                )

        # Paths
        for label, path in (
            ("App data root", paths.app_data_root),
            ("DB directory", paths.db_path.parent),
            ("Media root", paths.media_root),
            ("Logs dir", paths.logs_dir),
            ("Backups dir", paths.backups_dir),
            ("Temp dir", paths.temp_dir),
            ("Config dir", paths.prefs_path.parent),
        ):
            exists = path.exists()
            writable = path.exists() and path.is_dir()
            status = "PASS" if exists and writable else "FAIL"
            results.append(CheckResult("paths", label, status, f"exists={exists}"))

        # Backup validation (optional temp archive)
        if with_backup:
            backup_service = BackupService(paths, schema_version=database.schema_version, sync_protocol_version=SYNC_PROTOCOL_VERSION)
            with TemporaryDirectory(prefix="recipe_forge_release_check_") as tmp_dir:
                backup_path = Path(tmp_dir) / "readiness_backup.zip"
                created = backup_service.create_backup(backup_path)
                if created.total_bytes <= 0:
                    results.append(CheckResult("backup", "Backup size sanity", "WARN", "Backup archive has 0 bytes payload"))
                else:
                    results.append(CheckResult("backup", "Backup size sanity", "PASS", f"{created.total_bytes} bytes"))
                validated = backup_service.validate_backup(backup_path)
                results.append(
                    CheckResult(
                        "backup",
                        "Backup validation",
                        "PASS" if validated["ok"] else "FAIL",
                        "ok" if validated["ok"] else "; ".join(validated["errors"]),
                    )
                )
        else:
            results.append(CheckResult("backup", "Backup validation", "WARN", "Skipped (--with-backup not set)"))

        # Optional tests
        if with_tests:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "desktop/tests", "-q"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
            )
            status = "PASS" if completed.returncode == 0 else "FAIL"
            tail = completed.stdout.strip().splitlines()
            short = tail[-1] if tail else completed.stderr.strip() or "No test output"
            results.append(CheckResult("tests", "Desktop test suite", status, short))
        else:
            results.append(CheckResult("tests", "Desktop test suite", "WARN", "Skipped (--with-tests not set)"))
    finally:
        if database is not None:
            database.close()
    overall, actions = _summarize(results)
    return results, overall, actions


def render_report(results: list[CheckResult], overall: str, actions: list[str]) -> str:
    grouped: dict[str, list[CheckResult]] = {}
    for result in results:
        grouped.setdefault(result.category, []).append(result)
    lines: list[str] = []
    lines.append("Release Readiness Report")
    lines.append("=" * 24)
    for category in ("versioning", "data", "media", "backup", "paths", "tests"):
        entries = grouped.get(category, [])
        if not entries:
            continue
        lines.append("")
        lines.append(category.capitalize())
        for result in entries:
            lines.append(_line(result))
    lines.append("")
    lines.append("Summary")
    lines.append(f"- Overall status: {overall}")
    if actions:
        lines.append("- Recommended actions:")
        for action in actions:
            lines.append(f"  - {action}")
    else:
        lines.append("- Recommended actions: none")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate pre-release readiness report")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--with-backup", action="store_true", help="Create and validate temporary backup")
    parser.add_argument("--with-tests", action="store_true", help="Run desktop test suite")
    parser.add_argument("--verbose", action="store_true", help="Include detailed media id lists")
    args = parser.parse_args()

    results, overall, actions = run_readiness_checks(
        project_root=Path(args.project_root).resolve(),
        with_backup=bool(args.with_backup),
        with_tests=bool(args.with_tests),
        verbose=bool(args.verbose),
    )
    print(render_report(results, overall, actions))
    return 0 if overall != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
