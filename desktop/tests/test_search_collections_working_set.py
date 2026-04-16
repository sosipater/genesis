import json
from pathlib import Path

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.recipe_search_service import RecipeSearchFilters, RecipeSearchService


def _load_sample_recipe() -> Recipe:
    root = Path(__file__).resolve().parents[2]
    sample = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    return Recipe.from_dict(sample)


def test_search_matches_across_recipe_graph() -> None:
    recipe = _load_sample_recipe()
    recipe.title = "Smoky Tomato Pasta"
    recipe.ingredients[0].raw_text = "2 cups tomatoes"
    recipe.equipment[0].name = "Cast iron pan"
    recipe.steps[0].body_text = "Simmer tomatoes in pan"
    service = RecipeSearchService()

    results = service.search([recipe], "tomatoes", RecipeSearchFilters(scope="local"))
    assert len(results) == 1
    assert results[0].recipe.id == recipe.id


def test_collections_and_working_set_membership(tmp_path: Path) -> None:
    recipe = _load_sample_recipe()
    db = Database(tmp_path / "collections.db")
    try:
        repo = RecipeRepository(db.conn)
        repo.create_recipe(recipe)
        collection_id = repo.create_collection("Weeknight")
        repo.add_recipe_to_collection(collection_id, recipe.id)
        assert repo.list_collection_recipe_ids(collection_id) == [recipe.id]

        repo.add_to_working_set(recipe.id)
        assert repo.list_working_set_recipe_ids() == [recipe.id]

        repo.remove_from_working_set(recipe.id)
        assert repo.list_working_set_recipe_ids() == []
    finally:
        db.close()
