import json
from pathlib import Path
from uuid import uuid4

import pytest

from desktop.app.domain.models import Recipe, RecipeIngredientItem
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.recipe_share_service import USER_FACING_SHARE_MEDIA_BLOCKED, RecipeShareService


def _sample_recipe() -> Recipe:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    payload["scope"] = "local"
    return Recipe.from_dict(payload)


def test_export_package_structure_and_determinism(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    db = Database(tmp_path / "share.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _sample_recipe()
        repo.create_recipe(recipe)
        service = RecipeShareService(repo, root)
        output = tmp_path / "package.json"
        result = service.export_recipes([recipe.id], output)
        assert result.recipe_count == 1
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["share_format_version"] == 1
        assert payload["recipes"][0]["id"] == recipe.id
        # deterministic ordering for same recipe selection
        service.export_recipes([recipe.id], output)
        payload2 = json.loads(output.read_text(encoding="utf-8"))
        assert [item["id"] for item in payload2["recipes"]] == [item["id"] for item in payload["recipes"]]
    finally:
        db.close()


def test_import_collision_and_repeated_import_safety(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    db = Database(tmp_path / "import.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _sample_recipe()
        repo.create_recipe(recipe)
        service = RecipeShareService(repo, root)
        package = tmp_path / "share.json"
        service.export_recipes([recipe.id], package)

        first = service.import_package(package, "test-share")
        second = service.import_package(package, "test-share")
        assert first.imported_count == 1
        assert second.imported_count == 0
        assert second.skipped_count == 1
        assert second.collisions
    finally:
        db.close()


def test_import_preserves_links_and_timers(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    db = Database(tmp_path / "integrity.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _sample_recipe()
        repo.create_recipe(recipe)
        service = RecipeShareService(repo, root)
        package = tmp_path / "integrity.json"
        service.export_recipes([recipe.id], package)
        result = service.import_package(package, "integrity")
        assert result.imported_count == 1
        imported = [item for item in repo.list_recipes(include_deleted=False) if item.imported_from_recipe_id == recipe.id]
        assert len(imported) == 1
        assert len(imported[0].step_links) == len(recipe.step_links)
        assert len(imported[0].steps[0].timers) == len(recipe.steps[0].timers)
    finally:
        db.close()


def test_export_blocked_when_recipe_has_cover_media(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    db = Database(tmp_path / "media_block.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _sample_recipe()
        recipe.cover_media_id = "test-media-id"
        repo.create_recipe(recipe)
        service = RecipeShareService(repo, root)
        output = tmp_path / "blocked.json"
        with pytest.raises(ValueError) as excinfo:
            service.export_recipes([recipe.id], output)
        message = str(excinfo.value)
        assert recipe.id in message
        assert USER_FACING_SHARE_MEDIA_BLOCKED in message
    finally:
        db.close()


def test_import_validation_failure(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    db = Database(tmp_path / "invalid.db")
    try:
        repo = RecipeRepository(db.conn)
        service = RecipeShareService(repo, root)
        package = tmp_path / "invalid.json"
        package.write_text(json.dumps({"share_format_version": 1, "recipes": []}), encoding="utf-8")
        result = service.import_package(package)
        assert result.imported_count == 0
        assert result.errors
    finally:
        db.close()


def test_export_includes_transitive_sub_recipes(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    db = Database(tmp_path / "closure.db")
    try:
        repo = RecipeRepository(db.conn)
        base_id, parent_id = str(uuid4()), str(uuid4())
        now = "2026-04-15T12:00:00Z"
        base = Recipe(
            id=base_id,
            scope="local",
            title="Sauce",
            status="published",
            created_at=now,
            updated_at=now,
            equipment=[],
            ingredients=[
                RecipeIngredientItem(
                    id=str(uuid4()),
                    raw_text="1 cup milk",
                    is_optional=False,
                    display_order=0,
                    quantity_value=1.0,
                    unit="cup",
                    ingredient_name="milk",
                )
            ],
            steps=[],
        )
        parent = Recipe(
            id=parent_id,
            scope="local",
            title="Main",
            status="published",
            created_at=now,
            updated_at=now,
            equipment=[],
            ingredients=[
                RecipeIngredientItem(
                    id=str(uuid4()),
                    raw_text="Uses 1× Sauce",
                    is_optional=False,
                    display_order=0,
                    sub_recipe_id=base_id,
                    sub_recipe_usage_type="full_batch",
                    sub_recipe_display_name="Sauce",
                )
            ],
            steps=[],
        )
        repo.create_recipe(base)
        repo.create_recipe(parent)
        service = RecipeShareService(repo, root)
        out = tmp_path / "closure.json"
        result = service.export_recipes([parent_id], out)
        assert result.recipe_count == 2
        payload = json.loads(out.read_text(encoding="utf-8"))
        ids = {r["id"] for r in payload["recipes"]}
        assert ids == {base_id, parent_id}
    finally:
        db.close()


def test_import_rejects_orphan_sub_recipe_reference(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    db = Database(tmp_path / "orphan.db")
    try:
        repo = RecipeRepository(db.conn)
        service = RecipeShareService(repo, root)
        missing = str(uuid4())
        sample = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
        rid, iid, sid = str(uuid4()), str(uuid4()), str(uuid4())
        sample["id"] = rid
        sample["ingredients"] = [
            {
                "id": iid,
                "raw_text": "Uses missing sub-recipe",
                "quantity_value": None,
                "quantity_text": None,
                "unit": None,
                "ingredient_name": None,
                "preparation_notes": None,
                "substitutions": None,
                "affiliate_url": None,
                "recommended_product": None,
                "media_id": None,
                "is_optional": False,
                "display_order": 0,
                "catalog_ingredient_id": None,
                "sub_recipe_id": missing,
                "sub_recipe_usage_type": "full_batch",
                "sub_recipe_multiplier": None,
                "sub_recipe_display_name": "Ghost",
            }
        ]
        sample["steps"] = [
            {
                "id": sid,
                "title": "Do",
                "body_text": "Prepare.",
                "display_order": 0,
                "step_type": "instruction",
                "estimated_seconds": None,
                "media_id": None,
                "timers": [],
            }
        ]
        sample["step_links"] = []
        bad = {
            "share_format_version": 1,
            "package_id": str(uuid4()),
            "exported_at_utc": "2026-04-15T12:00:00Z",
            "source_app": "test",
            "media_included": False,
            "recipes": [sample],
        }
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        result = service.import_package(path)
        assert result.imported_count == 0
        assert any("not included in this share package" in e for e in result.errors)
    finally:
        db.close()
