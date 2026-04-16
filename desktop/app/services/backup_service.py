"""Backup and restore workflows for desktop operational data."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from desktop.app.domain.models import utc_now_iso
from desktop.app.runtime_paths import RuntimePaths
from desktop.app.versioning import APP_ID, APP_VERSION, BACKUP_FORMAT_VERSION, RECIPE_SHARE_FORMAT_VERSION


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _collect_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted([path for path in base.rglob("*") if path.is_file()], key=lambda item: str(item))


@dataclass(slots=True)
class BackupCreateResult:
    backup_path: Path
    file_count: int
    total_bytes: int


class BackupService:
    def __init__(self, runtime_paths: RuntimePaths, schema_version: int, sync_protocol_version: int):
        self._paths = runtime_paths
        self._schema_version = schema_version
        self._sync_protocol_version = sync_protocol_version

    def create_backup(self, backup_path: Path) -> BackupCreateResult:
        if backup_path.suffix.lower() != ".zip":
            raise ValueError("Backup path must use .zip extension")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        files: list[tuple[Path, str, bytes]] = []
        total_bytes = 0

        def add_file(file_path: Path, archive_name: str) -> None:
            nonlocal total_bytes
            data = file_path.read_bytes()
            files.append((file_path, archive_name, data))
            total_bytes += len(data)

        if self._paths.db_path.exists():
            add_file(self._paths.db_path, "data/genesis.db")
        for file_path in _collect_files(self._paths.media_root):
            rel = file_path.relative_to(self._paths.media_root).as_posix()
            add_file(file_path, f"media/{rel}")
        if self._paths.prefs_path.exists():
            add_file(self._paths.prefs_path, "config/preferences.json")

        manifest = {
            "backup_format_version": BACKUP_FORMAT_VERSION,
            "created_at_utc": utc_now_iso(),
            "source_app_id": APP_ID,
            "source_app_version": APP_VERSION,
            "schema_version": self._schema_version,
            "sync_protocol_version": self._sync_protocol_version,
            "recipe_share_format_version": RECIPE_SHARE_FORMAT_VERSION,
            "files": [
                {
                    "archive_path": archive_name,
                    "size_bytes": len(data),
                    "sha256": _sha256_bytes(data),
                }
                for _, archive_name, data in files
            ],
        }

        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
            for _, archive_name, data in files:
                archive.writestr(archive_name, data)

        return BackupCreateResult(backup_path=backup_path, file_count=len(files), total_bytes=total_bytes)

    def validate_backup(self, backup_path: Path) -> dict:
        if not backup_path.exists():
            return {"ok": False, "errors": [f"Backup file does not exist: {backup_path}"]}
        errors: list[str] = []
        with zipfile.ZipFile(backup_path, "r") as archive:
            if "manifest.json" not in archive.namelist():
                return {"ok": False, "errors": ["manifest.json missing in backup archive"]}
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("backup_format_version") != BACKUP_FORMAT_VERSION:
                errors.append(
                    f"Unsupported backup format version: {manifest.get('backup_format_version')} (expected {BACKUP_FORMAT_VERSION})"
                )
            for entry in manifest.get("files", []):
                archive_path = entry["archive_path"]
                if archive_path not in archive.namelist():
                    errors.append(f"Missing archived file: {archive_path}")
                    continue
                data = archive.read(archive_path)
                if int(entry["size_bytes"]) != len(data):
                    errors.append(f"Size mismatch for {archive_path}")
                if entry["sha256"] != _sha256_bytes(data):
                    errors.append(f"Checksum mismatch for {archive_path}")
        return {"ok": not errors, "errors": errors}

    def restore_backup(self, backup_path: Path, *, allow_replace: bool) -> dict:
        validation = self.validate_backup(backup_path)
        if not validation["ok"]:
            return {"ok": False, "errors": validation["errors"]}

        has_existing_state = (
            self._paths.db_path.exists()
            or any(self._paths.media_root.glob("**/*"))
            or self._paths.prefs_path.exists()
        )
        if has_existing_state and not allow_replace:
            return {"ok": False, "errors": ["Target installation is not empty. Re-run with allow_replace=true."]}

        with zipfile.ZipFile(backup_path, "r") as archive:
            with TemporaryDirectory(prefix="genesis_restore_") as temp_root:
                temp_dir = Path(temp_root)
                archive.extractall(temp_dir)
                manifest = json.loads((temp_dir / "manifest.json").read_text(encoding="utf-8"))
                incoming_schema_version = int(manifest["schema_version"])
                if incoming_schema_version > self._schema_version:
                    return {
                        "ok": False,
                        "errors": [
                            f"Backup schema version {incoming_schema_version} is newer than this app supports ({self._schema_version})"
                        ],
                    }

                if allow_replace:
                    if self._paths.db_path.exists():
                        try:
                            self._paths.db_path.unlink()
                        except PermissionError:
                            return {
                                "ok": False,
                                "errors": [
                                    "Database file is locked. Close running desktop/sync-host instances before restore."
                                ],
                            }
                    if self._paths.media_root.exists():
                        shutil.rmtree(self._paths.media_root)
                    if self._paths.prefs_path.exists():
                        self._paths.prefs_path.unlink()
                    self._paths.ensure_dirs()

                db_src = temp_dir / "data" / "genesis.db"
                if not db_src.exists():
                    db_src = temp_dir / "data" / "recipe_forge.db"
                if db_src.exists():
                    self._paths.db_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(db_src, self._paths.db_path)
                media_src = temp_dir / "media"
                if media_src.exists():
                    self._paths.media_root.mkdir(parents=True, exist_ok=True)
                    for file_path in _collect_files(media_src):
                        rel = file_path.relative_to(media_src)
                        dest = self._paths.media_root / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest)
                prefs_src = temp_dir / "config" / "preferences.json"
                if prefs_src.exists():
                    self._paths.prefs_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(prefs_src, self._paths.prefs_path)

        return {"ok": True, "errors": []}
