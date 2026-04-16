"""Runtime path strategy for desktop operational data."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RuntimePaths:
    app_data_root: Path
    db_path: Path
    media_root: Path
    logs_dir: Path
    backups_dir: Path
    temp_dir: Path
    prefs_path: Path

    def ensure_dirs(self) -> None:
        self.app_data_root.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.prefs_path.parent.mkdir(parents=True, exist_ok=True)


def build_runtime_paths(project_root: Path) -> RuntimePaths:
    override = os.getenv("RECIPE_FORGE_DATA_DIR")
    if override:
        data_root = Path(override).expanduser().resolve()
    else:
        appdata = os.getenv("APPDATA")
        if appdata:
            data_root = Path(appdata) / "RecipeForge"
        else:
            data_root = Path.home() / ".recipe_forge"
    paths = RuntimePaths(
        app_data_root=data_root,
        db_path=data_root / "data" / "recipe_forge.db",
        media_root=data_root / "media",
        logs_dir=data_root / "logs",
        backups_dir=data_root / "backups",
        temp_dir=data_root / "temp",
        prefs_path=data_root / "config" / "preferences.json",
    )
    paths.ensure_dirs()
    return paths
