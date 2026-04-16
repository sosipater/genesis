import json
from pathlib import Path

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository


def _sample_recipe() -> Recipe:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    return Recipe.from_dict(payload)


def test_favorite_open_cooked_tracking(tmp_path: Path) -> None:
    db = Database(tmp_path / "user_state.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _sample_recipe()
        repo.create_recipe(recipe)
        repo.upsert_recipe_user_state(recipe.id, is_favorite=True)
        repo.upsert_recipe_user_state(recipe.id, mark_opened=True)
        repo.upsert_recipe_user_state(recipe.id, mark_cooked=True)
        state = repo.get_recipe_user_state(recipe.id)
        assert state is not None
        assert bool(state["is_favorite"]) is True
        assert int(state["open_count"]) == 1
        assert int(state["cook_count"]) == 1
        assert state["last_opened_at"] is not None
        assert state["last_cooked_at"] is not None
    finally:
        db.close()
