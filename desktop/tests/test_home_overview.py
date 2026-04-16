import json
from pathlib import Path

from desktop.app.bundled_loader import BundledContentLoader
from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.editor_service import EditorService


def _sample_recipe() -> Recipe:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    recipe = Recipe.from_dict(payload)
    recipe.servings = 2
    return recipe


def test_home_overview_today_week_and_quick_resume(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    db = Database(tmp_path / "home.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _sample_recipe()
        repo.create_recipe(recipe)
        repo.upsert_recipe_user_state(recipe.id, mark_opened=True)
        plan_id = repo.create_meal_plan("Weekly")
        repo.add_meal_plan_item(plan_id, recipe.id, planned_date="2026-04-15", meal_slot="dinner")
        repo.create_grocery_list(plan_id, "Weekly groceries")

        service = EditorService(repo, BundledContentLoader(root), root)
        overview = service.get_home_overview(today_date="2026-04-15")
        assert len(overview.today) == 1
        assert "2026-04-15" in overview.this_week
        assert overview.quick_recent_recipe_id == recipe.id
        assert overview.quick_latest_grocery_name == "Weekly groceries"
        assert overview.quick_active_meal_plan_name == "Weekly"
    finally:
        db.close()
