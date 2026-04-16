"""Catalog ingredient library: persistence, recipe link, sync entity."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository


def _minimal_recipe(rid: str, ing_id: str) -> Recipe:
    return Recipe.from_dict(
        {
            "id": rid,
            "scope": "local",
            "title": "T",
            "status": "draft",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
            "equipment": [],
            "ingredients": [
                {
                    "id": ing_id,
                    "raw_text": "2 cups flour",
                    "is_optional": False,
                    "display_order": 0,
                }
            ],
            "steps": [],
            "step_links": [],
            "tags": [],
            "schema_version": 1,
            "bundle_export_eligible": False,
            "export_bundle_recipe_version": 1,
            "is_forked_from_bundled": False,
            "display_settings": {},
        }
    )


def test_create_catalog_and_link_recipe_ingredient_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    try:
        repo = RecipeRepository(db.conn)
        cid = repo.create_catalog_ingredient("All-purpose flour", notes="AP")
        ing_id = str(uuid4())
        recipe = _minimal_recipe(str(uuid4()), ing_id)
        recipe.ingredients[0].catalog_ingredient_id = cid
        repo.create_recipe(recipe)
        loaded = repo.get_recipe_by_id(recipe.id)
        assert loaded is not None
        assert loaded.ingredients[0].catalog_ingredient_id == cid
        assert loaded.ingredients[0].raw_text == "2 cups flour"
    finally:
        db.close()


def test_catalog_edit_does_not_rewrite_recipe_snapshot(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    try:
        repo = RecipeRepository(db.conn)
        cid = repo.create_catalog_ingredient("flour")
        ing_id = str(uuid4())
        recipe = _minimal_recipe(str(uuid4()), ing_id)
        recipe.ingredients[0].catalog_ingredient_id = cid
        repo.create_recipe(recipe)
        now = "2025-06-01T12:00:00Z"
        repo.upsert_entity_change(
            "catalog_ingredient",
            {
                "id": cid,
                "name": "flour (updated canonical)",
                "notes": None,
                "normalized_name": "flour (updated canonical)",
                "created_at": "2020-01-01T00:00:00Z",
                "entity_version": 1,
            },
            now,
            "other-device",
        )
        loaded = repo.get_recipe_by_id(recipe.id)
        assert loaded is not None
        assert loaded.ingredients[0].raw_text == "2 cups flour"
        assert loaded.ingredients[0].catalog_ingredient_id == cid
    finally:
        db.close()


def test_sync_list_includes_catalog_ingredient_upsert_and_tombstone(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    try:
        repo = RecipeRepository(db.conn)
        cid = repo.create_catalog_ingredient("salt")
        changes = repo.list_entity_changes_since(None)
        types = {c["entity_type"] for c in changes if c["entity_id"] == cid}
        assert "catalog_ingredient" in types
        upserts = [c for c in changes if c["entity_type"] == "catalog_ingredient" and c["entity_id"] == cid]
        assert upserts[-1]["op"] == "upsert"
        assert upserts[-1]["body"]["name"] == "salt"

        tomb_time = "2025-07-01T00:00:00Z"
        repo.tombstone_entity("catalog_ingredient", cid, tomb_time, "desktop-local")
        after = repo.list_entity_changes_since(None)
        del_rows = [c for c in after if c["entity_type"] == "catalog_ingredient" and c["entity_id"] == cid and c["op"] == "delete"]
        assert del_rows
        assert del_rows[-1]["body"] is None
    finally:
        db.close()


def test_recipe_ingredient_sync_body_includes_catalog_id(tmp_path: Path) -> None:
    db = Database(tmp_path / "t.db")
    try:
        repo = RecipeRepository(db.conn)
        cid = repo.create_catalog_ingredient("butter")
        ing_id = str(uuid4())
        recipe = _minimal_recipe(str(uuid4()), ing_id)
        recipe.ingredients[0].catalog_ingredient_id = cid
        repo.create_recipe(recipe)
        body = repo._load_entity_body("recipe_ingredient_item", ing_id)
        assert body is not None
        assert body.get("catalog_ingredient_id") == cid
    finally:
        db.close()
