import json
from pathlib import Path

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.meal_plan_service import MealPlanService


def _sample_recipe() -> Recipe:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    recipe = Recipe.from_dict(payload)
    recipe.servings = 2
    recipe.ingredients[0].ingredient_name = "salt"
    recipe.ingredients[0].quantity_value = 1
    recipe.ingredients[0].unit = "tsp"
    return recipe


def test_scaling_and_grocery_aggregation(tmp_path: Path) -> None:
    recipe = _sample_recipe()
    db = Database(tmp_path / "scale.db")
    try:
        service = MealPlanService(repository=RecipeRepository(db.conn))
        items = service.generate_grocery_items([(recipe, 2.0)])
    finally:
        db.close()
    assert len(items) == 1
    assert items[0].name.lower() == "salt"
    assert items[0].quantity_value == 2.0
    assert items[0].unit == "tsp"


def test_meal_plan_and_grocery_persistence(tmp_path: Path) -> None:
    db = Database(tmp_path / "meal.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _sample_recipe()
        repo.create_recipe(recipe)
        meal_plan_id = repo.create_meal_plan("Week plan")
        item_id = repo.add_meal_plan_item(
            meal_plan_id,
            recipe.id,
            servings_override=4,
            planned_date="2026-04-20",
            meal_slot="dinner",
            sort_order=2,
        )
        items_for_plan = repo.list_meal_plan_items(meal_plan_id)
        assert len(items_for_plan) == 1
        assert items_for_plan[0]["planned_date"] == "2026-04-20"
        assert items_for_plan[0]["meal_slot"] == "dinner"
        repo.update_meal_plan_item_schedule(
            item_id,
            planned_date="2026-04-21",
            meal_slot="lunch",
            slot_label=None,
            sort_order=1,
        )
        updated_items = repo.list_meal_plan_items(meal_plan_id)
        assert updated_items[0]["planned_date"] == "2026-04-21"
        assert updated_items[0]["meal_slot"] == "lunch"

        grocery_id = repo.create_grocery_list(meal_plan_id, "Weekly")
        repo.replace_grocery_list_items(
            grocery_id,
            [{"name": "salt", "quantity_value": 2.0, "unit": "tsp", "checked": False, "source_recipe_ids": [recipe.id]}],
        )
        items = repo.list_grocery_list_items(grocery_id)
        assert len(items) == 1
        assert items[0]["name"] == "salt"

        manual_id = repo.add_manual_grocery_item(grocery_id, "paper towels", None, None)
        repo.update_grocery_item(manual_id, name="paper towels xl", quantity_value=None, unit=None)
        items = repo.list_grocery_list_items(grocery_id)
        assert any(item["source_type"] == "manual" for item in items)
        ordered = [item["id"] for item in items]
        repo.reorder_grocery_items(grocery_id, list(reversed(ordered)))
        reordered = repo.list_grocery_list_items(grocery_id)
        assert reordered[0]["id"] == ordered[-1]

        # Regeneration safety: create a new snapshot, old edited list remains intact.
        second_grocery_id = repo.create_grocery_list(meal_plan_id, "Weekly v2")
        assert second_grocery_id != grocery_id
        original_items = repo.list_grocery_list_items(grocery_id)
        assert any(item["name"] == "paper towels xl" for item in original_items)

        # Soft delete + restore for undo-safe meal plan management.
        repo.delete_meal_plan(meal_plan_id)
        assert not repo.list_meal_plans()
        repo.restore_meal_plan(meal_plan_id)
        assert len(repo.list_meal_plans()) == 1
    finally:
        db.close()
