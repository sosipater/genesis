from pathlib import Path

from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.runtime_paths import RuntimePaths
from desktop.app.services.backup_service import BackupService
from desktop.app.services.diagnostics_service import DiagnosticsService
from desktop.app.services.media_service import MediaService


def _runtime_paths(tmp_path: Path) -> RuntimePaths:
    return RuntimePaths(
        app_data_root=tmp_path / "appdata",
        db_path=tmp_path / "appdata" / "data" / "genesis.db",
        media_root=tmp_path / "appdata" / "media",
        logs_dir=tmp_path / "appdata" / "logs",
        backups_dir=tmp_path / "appdata" / "backups",
        temp_dir=tmp_path / "appdata" / "temp",
        prefs_path=tmp_path / "appdata" / "config" / "preferences.json",
    )


def test_backup_create_validate_and_restore_safety(tmp_path: Path) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    runtime_paths.ensure_dirs()
    db = Database(runtime_paths.db_path)
    try:
        repo = RecipeRepository(db.conn)
        media = MediaService(repo, runtime_paths.media_root)
        sample = tmp_path / "sample.jpg"
        sample.write_bytes(b"img")
        media.import_for_owner("recipe_cover", "recipe-1", sample)
        runtime_paths.prefs_path.write_text('{"theme":"dark"}', encoding="utf-8")

        backup_service = BackupService(runtime_paths, schema_version=db.schema_version, sync_protocol_version=1)
        backup_zip = tmp_path / "backup.zip"
        created = backup_service.create_backup(backup_zip)
        assert created.file_count >= 2

        validated = backup_service.validate_backup(backup_zip)
        assert validated["ok"] is True

        runtime_paths.db_path.write_bytes(b"dirty")
        denied = backup_service.restore_backup(backup_zip, allow_replace=False)
        assert denied["ok"] is False
        assert "not empty" in denied["errors"][0]

        db.close()
        restored = backup_service.restore_backup(backup_zip, allow_replace=True)
        assert restored["ok"] is True
    finally:
        if db.conn:
            try:
                db.close()
            except Exception:
                pass


def test_diagnostics_and_media_scan_report(tmp_path: Path) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    runtime_paths.ensure_dirs()
    db = Database(runtime_paths.db_path)
    try:
        repo = RecipeRepository(db.conn)
        media_service = MediaService(repo, runtime_paths.media_root)
        sample = tmp_path / "sample.jpg"
        sample.write_bytes(b"img")
        media_service.import_for_owner("recipe_cover", "recipe-1", sample)

        diagnostics = DiagnosticsService(
            repo,
            runtime_paths,
            media_service,
            schema_version=db.schema_version,
            sync_protocol_version=1,
        )
        report = diagnostics.full_report()
        assert report["version"]["schema_version"] == db.schema_version
        assert "app_data_root" in report["paths"]
        assert "orphan_assets" in report["media"]
    finally:
        db.close()
