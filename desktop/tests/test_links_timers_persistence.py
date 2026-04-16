import json
from pathlib import Path
from uuid import uuid4

from desktop.app.domain.models import Recipe, StepLink, StepTimer
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository


def test_links_and_timers_roundtrip(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    recipe = Recipe.from_dict(payload)
    step = recipe.steps[0]
    step.timers.append(
        StepTimer(
            id=str(uuid4()),
            label="Rest",
            duration_seconds=120,
            auto_start=True,
            alert_sound_key="bell",
        )
    )
    recipe.step_links.append(
        StepLink(
            id=str(uuid4()),
            step_id=step.id,
            target_type="equipment",
            target_id=recipe.equipment[0].id,
            token_key="pot",
            label_snapshot="Large pot",
            label_override=None,
        )
    )

    db = Database(tmp_path / "links_timers.db")
    try:
        repo = RecipeRepository(db.conn)
        repo.create_recipe(recipe)
        loaded = repo.get_recipe_by_id(recipe.id)
        assert loaded is not None
        assert len(loaded.step_links) == len(recipe.step_links)
        assert len(loaded.steps[0].timers) == len(recipe.steps[0].timers)
        assert any(link.target_type == "equipment" for link in loaded.step_links)
    finally:
        db.close()

