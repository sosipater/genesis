from pathlib import Path

from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.runtime_paths import RuntimePaths
from desktop.app.services.media_service import MediaService
from tools.release_readiness_report import render_report, run_readiness_checks


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


def test_release_report_structure_and_summary_pass(tmp_path: Path) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    runtime_paths.ensure_dirs()
    db = Database(runtime_paths.db_path)
    try:
        results, overall, actions = run_readiness_checks(
            project_root=Path(__file__).resolve().parents[2],
            with_backup=True,
            with_tests=False,
            verbose=False,
            runtime_paths=runtime_paths,
        )
        text = render_report(results, overall, actions)
        assert "Release Readiness Report" in text
        assert "Versioning" in text
        assert "Data" in text
        assert "Media" in text
        assert "Summary" in text
        assert overall in {"PASS", "WARN"}
    finally:
        db.close()


def test_release_report_missing_media_is_fail(tmp_path: Path) -> None:
    runtime_paths = _runtime_paths(tmp_path)
    runtime_paths.ensure_dirs()
    db = Database(runtime_paths.db_path)
    try:
        repo = RecipeRepository(db.conn)
        media = MediaService(repo, runtime_paths.media_root)
        sample = tmp_path / "sample.jpg"
        sample.write_bytes(b"img")
        asset = media.import_for_owner("recipe_cover", "recipe-1", sample)
        resolved = media.resolve_media_path(asset["id"])
        assert resolved is not None
        resolved.unlink()

        results, overall, actions = run_readiness_checks(
            project_root=Path(__file__).resolve().parents[2],
            with_backup=False,
            with_tests=False,
            verbose=False,
            runtime_paths=runtime_paths,
        )
        missing = [item for item in results if item.label == "Media missing files"]
        assert missing
        assert missing[0].status == "FAIL"
        assert overall == "FAIL"
        assert any("Media missing files" in action for action in actions)
    finally:
        db.close()
