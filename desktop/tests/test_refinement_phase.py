"""Tests for refinement phase: global equipment, tags, timers, search."""

import copy
import json
from pathlib import Path
from uuid import uuid4

from desktop.app.domain.models import Recipe, StepTimer
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.recipe_search_service import RecipeSearchFilters, RecipeSearchService
from desktop.app.ui.timer_alert_mapping import label_for_sound_key, sound_key_for_label


def _minimal_recipe() -> Recipe:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    return Recipe.from_dict(payload)


def test_global_equipment_create_and_recipe_link_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "ge.db")
    try:
        repo = RecipeRepository(db.conn)
        ge_id = repo.create_global_equipment("Dutch oven", notes="Heavy")
        recipe = _minimal_recipe()
        recipe.equipment[0].global_equipment_id = ge_id
        repo.create_recipe(recipe)
        loaded = repo.get_recipe_by_id(recipe.id)
        assert loaded is not None
        assert loaded.equipment[0].global_equipment_id == ge_id
    finally:
        db.close()


def test_recipe_tags_sync_recipe_tags_table(tmp_path: Path) -> None:
    db = Database(tmp_path / "tags.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _minimal_recipe()
        recipe.tags = ["Weeknight", "Vegetarian", "Weeknight"]
        repo.create_recipe(recipe)
        rows = db.conn.execute(
            """
            SELECT t.name FROM recipe_tags rt
            JOIN tags t ON t.id = rt.tag_id
            WHERE rt.recipe_id=? ORDER BY lower(t.name)
            """,
            (recipe.id,),
        ).fetchall()
        names = [r["name"] for r in rows]
        assert names == ["Vegetarian", "Weeknight"]
    finally:
        db.close()


def test_timer_alert_vibrate_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "vib.db")
    try:
        repo = RecipeRepository(db.conn)
        recipe = _minimal_recipe()
        step = recipe.steps[0]
        step.timers.append(
            StepTimer(
                id=str(uuid4()),
                label="Boil",
                duration_seconds=60,
                auto_start=False,
                alert_sound_key="alarm",
                alert_vibrate=True,
            )
        )
        repo.create_recipe(recipe)
        loaded = repo.get_recipe_by_id(recipe.id)
        assert loaded is not None
        t = loaded.steps[0].timers[-1]
        assert t.alert_sound_key == "alarm"
        assert t.alert_vibrate is True
    finally:
        db.close()


def test_timer_sound_mapping_roundtrip() -> None:
    assert sound_key_for_label("Alarm") == "alarm"
    assert label_for_sound_key("chime_soft") == "Soft chime"
    assert label_for_sound_key("unknown_custom_key") == "Default"


def test_library_tag_filter_requires_all_tags() -> None:
    base = _minimal_recipe()
    a = copy.deepcopy(base)
    a.tags = ["quick", "vegan"]
    b = copy.deepcopy(base)
    b.id = str(uuid4())
    b.tags = ["quick"]
    service = RecipeSearchService()
    res = service.search([a, b], "", RecipeSearchFilters(tags=["quick", "vegan"]))
    assert len(res) == 1
    assert "vegan" in res[0].recipe.tags
