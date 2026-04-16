"""Bundled content export workflow for eligible local recipes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from desktop.app.domain.models import Recipe, utc_now_iso
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.recipe_diff_service import RecipeDiffService


@dataclass(slots=True)
class BundleExportResult:
    content_version: str
    exported_count: int
    manifest_path: Path
    exported_files: list[Path]
    warnings: list[str]


class BundleExportService:
    def __init__(self, repository: RecipeRepository, project_root: Path):
        self._repository = repository
        self._root = project_root
        self._bundled_dir = self._root / "bundled_content"
        self._recipes_dir = self._bundled_dir / "recipes"
        self._manifest_path = self._bundled_dir / "manifest.json"
        self._diff_service = RecipeDiffService()

    def export_eligible(self, content_version: str) -> BundleExportResult:
        if not content_version.strip():
            raise ValueError("content_version is required")
        self._recipes_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._load_manifest()
        existing_by_id = {entry["id"]: entry for entry in manifest.get("bundled_recipes", [])}

        eligible = [
            recipe
            for recipe in self._repository.list_recipes(include_deleted=False)
            if recipe.bundle_export_eligible and recipe.scope == "local"
        ]
        exported_files: list[Path] = []
        bundled_entries: list[dict] = []
        seen_ids: set[str] = set()
        warnings: list[str] = []

        for recipe in sorted(eligible, key=lambda item: item.id):
            bundled_id = recipe.export_bundle_recipe_id or str(uuid4())
            if bundled_id in seen_ids:
                raise ValueError(f"Duplicate bundled export recipe id in selection: {bundled_id}")
            seen_ids.add(bundled_id)

            exported_payload = self._to_bundled_payload(recipe, bundled_id, content_version)
            recipe_file = self._recipes_dir / f"{bundled_id}.json"
            recipe_file.write_text(json.dumps(exported_payload, indent=2, sort_keys=True), encoding="utf-8")
            checksum = self._sha256(recipe_file)
            previous_entry = existing_by_id.get(bundled_id)
            previous_checksum = previous_entry["checksum_sha256"] if previous_entry else None
            if previous_entry and previous_checksum == checksum:
                bundled_version = int(previous_entry["version"])
            else:
                bundled_version = (int(previous_entry["version"]) + 1) if previous_entry else 1

            bundled_entries.append(
                {
                    "id": bundled_id,
                    "version": bundled_version,
                    "file": f"recipes/{recipe_file.name}",
                    "checksum_sha256": checksum,
                    "title_snapshot": recipe.title,
                    "source_local_recipe_id": recipe.id,
                }
            )
            exported_files.append(recipe_file)
            if previous_entry is not None:
                old_file = self._bundled_dir / previous_entry["file"]
                if old_file.exists():
                    old_payload = json.loads(old_file.read_text(encoding="utf-8"))
                    old_recipe = Recipe.from_dict(old_payload)
                    new_recipe = Recipe.from_dict(exported_payload)
                    diff = self._diff_service.diff_bundled_versions(old_recipe, new_recipe)
                    warnings.extend(self._build_export_warnings(diff, bundled_id))

            if recipe.export_bundle_recipe_id != bundled_id or recipe.export_bundle_recipe_version != bundled_version:
                recipe.export_bundle_recipe_id = bundled_id
                recipe.export_bundle_recipe_version = bundled_version
                recipe.updated_at = utc_now_iso()
                self._repository.update_recipe(recipe)

        bundled_entries.sort(key=lambda entry: entry["id"])
        manifest_payload = {
            "manifest_version": 1,
            "app_content_version": content_version,
            "generated_at_utc": utc_now_iso(),
            "bundled_recipes": bundled_entries,
            "checksums": {entry["file"]: entry["checksum_sha256"] for entry in bundled_entries},
            "migration_notes": manifest.get("migration_notes", []),
        }
        self._manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True), encoding="utf-8")
        return BundleExportResult(
            content_version=content_version,
            exported_count=len(bundled_entries),
            manifest_path=self._manifest_path,
            exported_files=exported_files,
            warnings=warnings,
        )

    def _to_bundled_payload(self, recipe: Recipe, bundled_id: str, content_version: str) -> dict:
        payload = recipe.to_dict()
        payload["id"] = bundled_id
        payload["scope"] = "bundled"
        payload["bundled_content_version"] = content_version
        payload["bundle_export_eligible"] = False
        payload["export_bundle_recipe_id"] = bundled_id
        payload["export_bundle_recipe_version"] = recipe.export_bundle_recipe_version
        payload["origin_bundled_recipe_id"] = None
        payload["origin_bundled_recipe_version"] = None
        payload["is_forked_from_bundled"] = False
        return payload

    def _load_manifest(self) -> dict:
        if not self._manifest_path.exists():
            return {
                "manifest_version": 1,
                "app_content_version": "0.0.0",
                "generated_at_utc": utc_now_iso(),
                "bundled_recipes": [],
                "checksums": {},
                "migration_notes": [],
            }
        return json.loads(self._manifest_path.read_text(encoding="utf-8"))

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _build_export_warnings(diff: dict, bundled_id: str) -> list[str]:
        warnings: list[str] = []
        if diff["steps"]["removed"]:
            warnings.append(f"{bundled_id}: steps removed ({len(diff['steps']['removed'])})")
        removed_required_equipment = [
            item for item in diff["equipment"]["removed"] if bool(item.get("is_required"))
        ]
        if removed_required_equipment:
            warnings.append(f"{bundled_id}: required equipment removed ({len(removed_required_equipment)})")
        if diff["summary"]["entities_removed"] >= 5:
            warnings.append(f"{bundled_id}: high removal count ({diff['summary']['entities_removed']})")
        return warnings

