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


def _default_data_root() -> Path:
    override = os.getenv("GENESIS_DATA_DIR") or os.getenv("RECIPE_FORGE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    appdata = os.getenv("APPDATA")
    if appdata:
        base = Path(appdata)
        genesis = base / "Genesis"
        legacy = base / "RecipeForge"
        if genesis.exists():
            return genesis
        if legacy.exists():
            return legacy
        return genesis
    home_genesis = Path.home() / ".genesis"
    home_legacy = Path.home() / ".recipe_forge"
    if home_genesis.exists():
        return home_genesis
    if home_legacy.exists():
        return home_legacy
    return home_genesis


def _resolve_db_path(data_root: Path) -> Path:
    data_dir = data_root / "data"
    genesis_db = data_dir / "genesis.db"
    legacy_db = data_dir / "recipe_forge.db"
    if genesis_db.exists():
        return genesis_db
    if legacy_db.exists():
        return legacy_db
    return genesis_db


def build_runtime_paths(project_root: Path) -> RuntimePaths:
    data_root = _default_data_root()
    paths = RuntimePaths(
        app_data_root=data_root,
        db_path=_resolve_db_path(data_root),
        media_root=data_root / "media",
        logs_dir=data_root / "logs",
        backups_dir=data_root / "backups",
        temp_dir=data_root / "temp",
        prefs_path=data_root / "config" / "preferences.json",
    )
    paths.ensure_dirs()
    return paths
