"""Operational diagnostics service."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.runtime_paths import RuntimePaths
from desktop.app.services.media_service import MediaService
from desktop.app.versioning import APP_ID, APP_VERSION, RECIPE_SHARE_FORMAT_VERSION


@dataclass(slots=True)
class VersionReport:
    app_id: str
    app_version: str
    schema_version: int
    sync_protocol_version: int
    recipe_share_format_version: int


class DiagnosticsService:
    def __init__(
        self,
        repository: RecipeRepository,
        runtime_paths: RuntimePaths,
        media_service: MediaService,
        schema_version: int,
        sync_protocol_version: int,
    ):
        self._repo = repository
        self._paths = runtime_paths
        self._media_service = media_service
        self._schema_version = schema_version
        self._sync_protocol_version = sync_protocol_version

    def version_report(self) -> VersionReport:
        return VersionReport(
            app_id=APP_ID,
            app_version=APP_VERSION,
            schema_version=self._schema_version,
            sync_protocol_version=self._sync_protocol_version,
            recipe_share_format_version=RECIPE_SHARE_FORMAT_VERSION,
        )

    def paths_report(self) -> dict:
        return {
            "app_data_root": str(self._paths.app_data_root),
            "db_path": str(self._paths.db_path),
            "media_root": str(self._paths.media_root),
            "logs_dir": str(self._paths.logs_dir),
            "backups_dir": str(self._paths.backups_dir),
            "temp_dir": str(self._paths.temp_dir),
            "prefs_path": str(self._paths.prefs_path),
        }

    def data_report(self) -> dict:
        return {
            "recipe_count": len(self._repo.list_recipes(include_deleted=False)),
            "meal_plan_count": len(self._repo.list_meal_plans()),
            "grocery_list_count": len(self._repo.list_grocery_lists()),
            "media_asset_count": len(self._repo.list_media_assets(include_deleted=False)),
        }

    def media_report(self) -> dict:
        return self._media_service.scan_health()

    def full_report(self) -> dict:
        return {
            "version": asdict(self.version_report()),
            "paths": self.paths_report(),
            "data": self.data_report(),
            "media": self.media_report(),
        }

    @staticmethod
    def format_report(report: dict) -> str:
        lines: list[str] = []
        lines.append("Version:")
        for key, value in report["version"].items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("Paths:")
        for key, value in report["paths"].items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("Data:")
        for key, value in report["data"].items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("Media Health:")
        lines.append(f"- media_root: {report['media']['media_root']}")
        lines.append(f"- asset_count: {report['media']['asset_count']}")
        lines.append(f"- orphan_assets: {len(report['media']['orphan_assets'])}")
        lines.append(f"- missing_files: {len(report['media']['missing_files'])}")
        lines.append(f"- dangling_references: {len(report['media']['dangling_references'])}")
        lines.append("")
        lines.append("Backups: use Create Backup in the main window for a portable zip (see backups_dir above).")
        return "\n".join(lines)
