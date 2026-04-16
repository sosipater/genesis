"""Desktop operational tooling: diagnostics, media scan, backup, restore."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.runtime_paths import build_runtime_paths
from desktop.app.services.backup_service import BackupService
from desktop.app.services.diagnostics_service import DiagnosticsService
from desktop.app.services.media_service import MediaService
from desktop.app.versioning import SYNC_PROTOCOL_VERSION


def _services(project_root: Path):
    runtime_paths = build_runtime_paths(project_root)
    database = Database(runtime_paths.db_path)
    repository = RecipeRepository(database.conn)
    media_service = MediaService(repository, runtime_paths.media_root)
    backup_service = BackupService(runtime_paths, schema_version=database.schema_version, sync_protocol_version=SYNC_PROTOCOL_VERSION)
    diagnostics_service = DiagnosticsService(
        repository,
        runtime_paths=runtime_paths,
        media_service=media_service,
        schema_version=database.schema_version,
        sync_protocol_version=SYNC_PROTOCOL_VERSION,
    )
    return database, media_service, backup_service, diagnostics_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Recipe Forge desktop operational tools")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    sub = parser.add_subparsers(dest="command", required=True)

    backup_parser = sub.add_parser("backup", help="Create backup zip")
    backup_parser.add_argument("--out", required=True, help="Backup output .zip path")

    validate_parser = sub.add_parser("validate-backup", help="Validate backup zip")
    validate_parser.add_argument("--path", required=True, help="Backup .zip path")

    restore_parser = sub.add_parser("restore", help="Restore backup zip")
    restore_parser.add_argument("--path", required=True, help="Backup .zip path")
    restore_parser.add_argument("--allow-replace", action="store_true", help="Allow replacing existing state")

    media_parser = sub.add_parser("media-scan", help="Scan media health")
    media_parser.add_argument("--cleanup-orphans", action="store_true", help="Delete orphan media records/files")

    sub.add_parser("diagnostics", help="Print diagnostics summary")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    database, media_service, backup_service, diagnostics_service = _services(project_root)
    try:
        if args.command == "backup":
            result = backup_service.create_backup(Path(args.out).resolve())
            print(json.dumps({"ok": True, "path": str(result.backup_path), "file_count": result.file_count}, indent=2))
            return 0
        if args.command == "validate-backup":
            result = backup_service.validate_backup(Path(args.path).resolve())
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 2
        if args.command == "restore":
            result = backup_service.restore_backup(Path(args.path).resolve(), allow_replace=bool(args.allow_replace))
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 2
        if args.command == "media-scan":
            report = media_service.scan_health()
            if args.cleanup_orphans and report["orphan_assets"]:
                report["cleanup"] = media_service.cleanup_orphan_assets(report["orphan_assets"])
            print(json.dumps(report, indent=2))
            return 0
        if args.command == "diagnostics":
            report = diagnostics_service.full_report()
            print(DiagnosticsService.format_report(report))
            return 0
        return 1
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
