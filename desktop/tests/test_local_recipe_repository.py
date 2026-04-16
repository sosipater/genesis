import json
from pathlib import Path

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository


def test_local_recipe_repository_crud(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    sample = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    recipe = Recipe.from_dict(sample)

    db = Database(tmp_path / "repo.db")
    try:
        repo = RecipeRepository(db.conn)
        repo.create_recipe(recipe)
        loaded = repo.get_recipe_by_id(recipe.id)
        assert loaded is not None
        assert loaded.title == recipe.title
        assert len(loaded.ingredients) == 1
        assert len(loaded.steps) == 1
        assert len(loaded.step_links) == 1

        recipe.title = "Updated title"
        recipe.updated_at = "2026-04-15T00:10:00Z"
        repo.update_recipe(recipe)
        loaded_after_update = repo.get_recipe_by_id(recipe.id)
        assert loaded_after_update is not None
        assert loaded_after_update.title == "Updated title"

        repo.delete_recipe(recipe.id, deleted_at="2026-04-15T01:00:00Z")
        loaded_after_delete = repo.get_recipe_by_id(recipe.id)
        assert loaded_after_delete is not None
        assert loaded_after_delete.deleted_at == "2026-04-15T01:00:00Z"
    finally:
        db.close()

