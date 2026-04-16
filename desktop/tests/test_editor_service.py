import json
from pathlib import Path

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.editor_service import EditorService


class FakeBundledLoader:
    def __init__(self, recipe: Recipe):
        self._recipe = recipe

    def load_bundled_recipes(self) -> list[Recipe]:
        return [self._recipe]


def test_duplicate_bundled_to_local_flow(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    payload["scope"] = "bundled"
    payload["bundled_content_version"] = "0.1.0"
    bundled_recipe = Recipe.from_dict(payload)

    db = Database(tmp_path / "editor.db")
    try:
        repo = RecipeRepository(db.conn)
        service = EditorService(repo, FakeBundledLoader(bundled_recipe), root)
        duplicated = service.duplicate_bundled_to_local(bundled_recipe.id)
        assert duplicated.scope == "local"
        assert duplicated.id != bundled_recipe.id
        assert duplicated.title.endswith("(Copy)")
        assert duplicated.is_forked_from_bundled is True
        assert duplicated.origin_bundled_recipe_id == bundled_recipe.id

        service.save_recipe(duplicated)
        loaded = repo.get_recipe_by_id(duplicated.id)
        assert loaded is not None
        assert loaded.scope == "local"
        assert loaded.is_forked_from_bundled is True
        assert loaded.origin_bundled_recipe_id == bundled_recipe.id
    finally:
        db.close()


def test_bundled_update_does_not_overwrite_local_fork(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    payload["scope"] = "bundled"
    payload["bundled_content_version"] = "1.0.0"
    bundled_recipe = Recipe.from_dict(payload)
    loader = FakeBundledLoader(bundled_recipe)

    db = Database(tmp_path / "editor_update.db")
    try:
        repo = RecipeRepository(db.conn)
        service = EditorService(repo, loader, root)
        fork = service.duplicate_bundled_to_local(bundled_recipe.id)
        fork.title = "My Local Fork"
        service.save_recipe(fork)

        # Simulate bundled content update from app release
        bundled_recipe.title = "Bundled Updated Title"
        bundled_recipe.bundled_content_version = "1.1.0"

        local_loaded = repo.get_recipe_by_id(fork.id)
        assert local_loaded is not None
        assert local_loaded.title == "My Local Fork"
        assert local_loaded.origin_bundled_recipe_id == bundled_recipe.id
    finally:
        db.close()


def test_compare_local_with_origin_returns_structured_diff(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    payload["scope"] = "bundled"
    payload["bundled_content_version"] = "1.0.0"
    bundled_recipe = Recipe.from_dict(payload)
    db = Database(tmp_path / "editor_diff.db")
    try:
        repo = RecipeRepository(db.conn)
        service = EditorService(repo, FakeBundledLoader(bundled_recipe), root)
        fork = service.duplicate_bundled_to_local(bundled_recipe.id)
        fork.title = "Fork Title"
        service.save_recipe(fork)
        diff = service.compare_local_with_origin(fork)
        assert "recipe_metadata_changes" in diff
        assert "summary" in diff
        assert "title" in diff["recipe_metadata_changes"]
    finally:
        db.close()

