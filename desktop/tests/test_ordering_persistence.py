import json
from pathlib import Path

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository


def test_ordering_persistence_for_steps_and_ingredients(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    recipe = Recipe.from_dict(payload)

    extra_step = Recipe.from_dict(payload).steps[0]
    extra_step.id = "123e4567-e89b-12d3-a456-426614174032"
    extra_step.body_text = "Second step"
    extra_step.display_order = 1
    recipe.steps.append(extra_step)

    recipe.ingredients[0].display_order = 1
    second_ing = Recipe.from_dict(payload).ingredients[0]
    second_ing.id = "123e4567-e89b-12d3-a456-426614174021"
    second_ing.raw_text = "pepper"
    second_ing.display_order = 0
    recipe.ingredients.append(second_ing)

    db = Database(tmp_path / "ordering.db")
    try:
        repo = RecipeRepository(db.conn)
        repo.create_recipe(recipe)
        loaded = repo.get_recipe_by_id(recipe.id)
        assert loaded is not None
        assert loaded.ingredients[0].raw_text == "pepper"
        assert loaded.steps[1].body_text == "Second step"
    finally:
        db.close()

