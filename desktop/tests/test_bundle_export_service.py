import json
from pathlib import Path
from uuid import uuid4

import pytest

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.bundle_export_service import BundleExportService


def _load_sample_recipe(root: Path) -> Recipe:
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    return Recipe.from_dict(payload)


def test_bundle_export_workflow_and_versioning(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    project = tmp_path / "project"
    (project / "bundled_content" / "recipes").mkdir(parents=True)
    (project / "bundled_content").joinpath("manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "app_content_version": "0.0.0",
                "generated_at_utc": "2026-04-15T00:00:00Z",
                "bundled_recipes": [],
                "checksums": {},
                "migration_notes": [],
            }
        ),
        encoding="utf-8",
    )

    db = Database(project / "desktop" / "data" / "genesis.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _load_sample_recipe(root)
        recipe.bundle_export_eligible = True
        repo.create_recipe(recipe)
        exporter = BundleExportService(repo, project)

        first = exporter.export_eligible("1.0.0")
        assert first.exported_count == 1
        assert first.warnings == []
        manifest = json.loads((project / "bundled_content" / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["app_content_version"] == "1.0.0"
        assert manifest["bundled_recipes"][0]["version"] == 1

        loaded = repo.get_recipe_by_id(recipe.id)
        assert loaded is not None
        assert loaded.export_bundle_recipe_id is not None
        assert loaded.export_bundle_recipe_version == 1

        loaded.title = "Changed Title"
        repo.update_recipe(loaded)
        second = exporter.export_eligible("1.0.1")
        assert second.exported_count == 1
        manifest2 = json.loads((project / "bundled_content" / "manifest.json").read_text(encoding="utf-8"))
        assert manifest2["bundled_recipes"][0]["version"] == 2
        assert second.warnings == []
    finally:
        db.close()


def test_export_rejects_duplicate_bundled_ids(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    project = tmp_path / "project"
    (project / "bundled_content" / "recipes").mkdir(parents=True)
    (project / "bundled_content").joinpath("manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "app_content_version": "0.0.0",
                "generated_at_utc": "2026-04-15T00:00:00Z",
                "bundled_recipes": [],
                "checksums": {},
                "migration_notes": [],
            }
        ),
        encoding="utf-8",
    )

    db = Database(project / "desktop" / "data" / "genesis.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe1 = _load_sample_recipe(root)
        recipe1.id = str(uuid4())
        recipe1.bundle_export_eligible = True
        recipe2 = _load_sample_recipe(root)
        recipe2.id = str(uuid4())
        recipe2.bundle_export_eligible = True
        shared_export_id = str(uuid4())
        recipe1.export_bundle_recipe_id = shared_export_id
        recipe2.export_bundle_recipe_id = shared_export_id
        repo.create_recipe(recipe1)
        repo.create_recipe(recipe2)

        exporter = BundleExportService(repo, project)
        with pytest.raises(ValueError):
            exporter.export_eligible("2.0.0")
    finally:
        db.close()

