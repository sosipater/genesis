import json
from pathlib import Path
from uuid import uuid4

from desktop.app.domain.models import Recipe, RecipeIngredientItem
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
        items, warnings = service.generate_grocery_items([(recipe, 2.0)])
    finally:
        db.close()
    assert not warnings
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


def _minimal_recipe(*, rid: str, title: str, ingredients: list[RecipeIngredientItem]) -> Recipe:
    now = "2026-04-15T12:00:00Z"
    return Recipe(
        id=rid,
        scope="local",
        title=title,
        status="published",
        created_at=now,
        updated_at=now,
        equipment=[],
        ingredients=ingredients,
        steps=[],
    )


def test_sub_recipe_full_batch_expansion(tmp_path: Path) -> None:
    base_id = str(uuid4())
    parent_id = str(uuid4())
    base = _minimal_recipe(
        rid=base_id,
        title="Sauce",
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
    )
    parent = _minimal_recipe(
        rid=parent_id,
        title="Main",
        ingredients=[
            RecipeIngredientItem(
                id=str(uuid4()),
                raw_text=f"Uses 1× {base.title}",
                is_optional=False,
                display_order=0,
                sub_recipe_id=base_id,
                sub_recipe_usage_type="full_batch",
                sub_recipe_display_name=base.title,
            ),
            RecipeIngredientItem(
                id=str(uuid4()),
                raw_text="1 tsp salt",
                is_optional=False,
                display_order=1,
                quantity_value=1.0,
                unit="tsp",
                ingredient_name="salt",
            ),
        ],
    )
    db = Database(tmp_path / "sub.db")
    try:
        repo = RecipeRepository(db.conn)
        repo.create_recipe(base)
        repo.create_recipe(parent)
        service = MealPlanService(repository=repo)
        items, warnings = service.generate_grocery_items([(parent, 2.0)])
    finally:
        db.close()
    assert not warnings
    by_name = {i.name.lower(): i for i in items}
    assert "milk" in by_name
    assert by_name["milk"].quantity_value == 2.0
    assert "salt" in by_name
    assert by_name["salt"].quantity_value == 2.0


def test_sub_recipe_fraction_multiplier(tmp_path: Path) -> None:
    base_id = str(uuid4())
    parent_id = str(uuid4())
    base = _minimal_recipe(
        rid=base_id,
        title="Sauce",
        ingredients=[
            RecipeIngredientItem(
                id=str(uuid4()),
                raw_text="200 g sugar",
                is_optional=False,
                display_order=0,
                quantity_value=200.0,
                unit="g",
                ingredient_name="sugar",
            )
        ],
    )
    parent = _minimal_recipe(
        rid=parent_id,
        title="Main",
        ingredients=[
            RecipeIngredientItem(
                id=str(uuid4()),
                raw_text="Uses 0.5× Sauce",
                is_optional=False,
                display_order=0,
                sub_recipe_id=base_id,
                sub_recipe_usage_type="fraction_of_batch",
                sub_recipe_multiplier=0.5,
                sub_recipe_display_name="Sauce",
            ),
        ],
    )
    db = Database(tmp_path / "frac.db")
    try:
        repo = RecipeRepository(db.conn)
        repo.create_recipe(base)
        repo.create_recipe(parent)
        service = MealPlanService(repository=repo)
        items, warnings = service.generate_grocery_items([(parent, 2.0)])
    finally:
        db.close()
    assert not warnings
    sugar = next(i for i in items if "sugar" in i.name.lower())
    assert sugar.quantity_value == 200.0 * 2.0 * 0.5


def test_sub_recipe_cycle_and_missing(tmp_path: Path) -> None:
    a, b = str(uuid4()), str(uuid4())
    ra = _minimal_recipe(
        rid=a,
        title="A",
        ingredients=[
            RecipeIngredientItem(
                id=str(uuid4()),
                raw_text="Uses 1× B",
                is_optional=False,
                display_order=0,
                sub_recipe_id=b,
                sub_recipe_usage_type="full_batch",
                sub_recipe_display_name="B",
            )
        ],
    )
    rb = _minimal_recipe(
        rid=b,
        title="B",
        ingredients=[
            RecipeIngredientItem(
                id=str(uuid4()),
                raw_text="Uses 1× A",
                is_optional=False,
                display_order=0,
                sub_recipe_id=a,
                sub_recipe_usage_type="full_batch",
                sub_recipe_display_name="A",
            )
        ],
    )
    missing_parent = str(uuid4())
    missing_line_id = str(uuid4())
    rm = _minimal_recipe(
        rid=missing_parent,
        title="Has missing",
        ingredients=[
            RecipeIngredientItem(
                id=missing_line_id,
                raw_text="Uses 1× Ghost",
                is_optional=False,
                display_order=0,
                sub_recipe_id=str(uuid4()),
                sub_recipe_usage_type="full_batch",
                sub_recipe_display_name="Ghost",
            )
        ],
    )
    db = Database(tmp_path / "cycle.db")
    try:
        repo = RecipeRepository(db.conn)
        repo.create_recipe(ra)
        repo.create_recipe(rb)
        repo.create_recipe(rm)
        service = MealPlanService(repository=repo)
        _, warnings = service.generate_grocery_items([(ra, 1.0)])
        assert any("circular" in w.lower() for w in warnings)
        items2, w2 = service.generate_grocery_items([(rm, 1.0)])
        assert any("missing" in w.lower() for w in w2)
        assert any("[missing recipe]" in i.name.lower() for i in items2)
    finally:
        db.close()


def test_sub_recipe_fields_round_trip_through_repository(tmp_path: Path) -> None:
    base_id = str(uuid4())
    parent_id = str(uuid4())
    base = _minimal_recipe(
        rid=base_id,
        title="Sauce",
        ingredients=[
            RecipeIngredientItem(
                id=str(uuid4()),
                raw_text="1 g x",
                is_optional=False,
                display_order=0,
                quantity_value=1.0,
                unit="g",
                ingredient_name="x",
            )
        ],
    )
    parent = _minimal_recipe(
        rid=parent_id,
        title="Main",
        ingredients=[
            RecipeIngredientItem(
                id=str(uuid4()),
                raw_text="Uses 1× Sauce",
                is_optional=False,
                display_order=0,
                sub_recipe_id=base_id,
                sub_recipe_usage_type="full_batch",
                sub_recipe_display_name="Sauce",
            ),
        ],
    )
    db = Database(tmp_path / "roundtrip.db")
    try:
        repo = RecipeRepository(db.conn)
        repo.create_recipe(base)
        repo.create_recipe(parent)
        loaded = repo.get_recipe_by_id(parent_id)
        assert loaded is not None
        ing0 = loaded.ingredients[0]
        assert ing0.sub_recipe_id == base_id
        assert ing0.sub_recipe_usage_type == "full_batch"
        assert ing0.sub_recipe_display_name == "Sauce"
    finally:
        db.close()
