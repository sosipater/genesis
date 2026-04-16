"""Managed local media storage service."""

from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path
from uuid import uuid4

from desktop.app.domain.models import utc_now_iso
from desktop.app.persistence.recipe_repository import RecipeRepository


class MediaService:
    _ALLOWED_MIME_PREFIXES = ("image/",)
    _MAX_BYTES = 15 * 1024 * 1024

    def __init__(self, repository: RecipeRepository, media_root: Path):
        self._repo = repository
        self._media_root = media_root
        self._media_root.mkdir(parents=True, exist_ok=True)

    def import_for_owner(self, owner_type: str, owner_id: str, source_path: Path) -> dict:
        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"Media source file not found: {source_path}")
        file_size = source_path.stat().st_size
        if file_size > self._MAX_BYTES:
            raise ValueError(f"Media file exceeds max size ({self._MAX_BYTES} bytes): {source_path.name}")
        media_id = str(uuid4())
        ext = source_path.suffix.lower() or ".bin"
        file_name = source_path.name
        relative_path = f"{owner_type}/{media_id}{ext}"
        destination = self._media_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        mime_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        if not any(mime_type.startswith(prefix) for prefix in self._ALLOWED_MIME_PREFIXES):
            destination.unlink(missing_ok=True)
            raise ValueError(f"Unsupported media type {mime_type}. Only image files are allowed.")
        now = utc_now_iso()
        self._repo.upsert_media_asset(
            id=media_id,
            owner_type=owner_type,
            owner_id=owner_id,
            file_name=file_name,
            mime_type=mime_type,
            relative_path=relative_path,
            updated_at=now,
        )
        return self._repo.get_media_asset(media_id) or {
            "id": media_id,
            "owner_type": owner_type,
            "owner_id": owner_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "relative_path": relative_path,
            "updated_at": now,
        }

    def remove_media(self, media_asset_id: str) -> None:
        asset = self._repo.get_media_asset(media_asset_id)
        if asset:
            relative = asset.get("relative_path")
            if relative:
                path = self._media_root / relative
                if path.exists():
                    path.unlink()
        self._repo.delete_media_asset(media_asset_id)

    def resolve_media_path(self, media_asset_id: str) -> Path | None:
        asset = self._repo.get_media_asset(media_asset_id)
        if not asset:
            return None
        relative = asset.get("relative_path")
        if not relative:
            return None
        candidate = self._media_root / relative
        if not candidate.exists():
            return None
        return candidate

    def scan_health(self) -> dict:
        assets = self._repo.list_media_assets(include_deleted=False)
        active_ids = {asset["id"] for asset in assets}
        referenced_ids: set[str] = set()

        for recipe in self._repo.list_recipes(include_deleted=False):
            if recipe.cover_media_id:
                referenced_ids.add(recipe.cover_media_id)
            for item in recipe.equipment:
                if item.media_id:
                    referenced_ids.add(item.media_id)
            for item in recipe.ingredients:
                if item.media_id:
                    referenced_ids.add(item.media_id)
            for step in recipe.steps:
                if step.media_id:
                    referenced_ids.add(step.media_id)

        orphan_assets = sorted(active_ids - referenced_ids)
        missing_files: list[str] = []
        for asset in assets:
            relative = asset.get("relative_path")
            if not relative:
                missing_files.append(asset["id"])
                continue
            if not (self._media_root / relative).exists():
                missing_files.append(asset["id"])
        dangling_references = sorted(referenced_ids - active_ids)
        return {
            "media_root": str(self._media_root),
            "asset_count": len(assets),
            "orphan_assets": orphan_assets,
            "missing_files": sorted(missing_files),
            "dangling_references": dangling_references,
        }

    def cleanup_orphan_assets(self, orphan_ids: list[str]) -> dict:
        removed: list[str] = []
        for media_asset_id in orphan_ids:
            asset = self._repo.get_media_asset(media_asset_id)
            if asset:
                relative = asset.get("relative_path")
                if relative:
                    path = self._media_root / relative
                    if path.exists():
                        path.unlink()
            self._repo.delete_media_asset(media_asset_id)
            removed.append(media_asset_id)
        return {"removed_count": len(removed), "removed_ids": removed}
