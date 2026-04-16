import json
from pathlib import Path
from uuid import uuid4

import pytest

from desktop.app.domain.models import Recipe, RecipeStep, StepLink
from desktop.app.services.recipe_diff_service import RecipeDiffService


def _sample_recipe() -> Recipe:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    return Recipe.from_dict(payload)


def test_diff_detects_metadata_entity_and_order_changes() -> None:
    old_recipe = _sample_recipe()
    new_recipe = _sample_recipe()
    new_recipe.title = "Changed"

    new_recipe.ingredients[0].raw_text = "different"
    new_recipe.ingredients[0].display_order = 2
    new_recipe.equipment.append(
        old_recipe.equipment[0].__class__(
            id=str(uuid4()),
            name="Skillet",
            is_required=False,
            display_order=1,
        )
    )
    new_recipe.steps.append(
        RecipeStep(
            id=str(uuid4()),
            title="Extra",
            body_text="Extra step",
            step_type="instruction",
            estimated_seconds=None,
            display_order=1,
        )
    )
    new_recipe.step_links.append(
        StepLink(
            id=str(uuid4()),
            step_id=new_recipe.steps[0].id,
            target_type="equipment",
            target_id=new_recipe.equipment[0].id,
            token_key="pot",
            label_snapshot="pot",
        )
    )
    diff = RecipeDiffService().diff_recipes(old_recipe, new_recipe)
    assert "title" in diff["recipe_metadata_changes"]
    assert len(diff["equipment"]["added"]) == 1
    assert len(diff["ingredients"]["modified"]) >= 1
    assert diff["ingredients"]["order_changed"] is True
    assert len(diff["steps"]["added"]) == 1
    assert len(diff["step_links"]["added"]) == 1


def test_diff_is_deterministic() -> None:
    old_recipe = _sample_recipe()
    new_recipe = _sample_recipe()
    new_recipe.title = "Changed Again"
    service = RecipeDiffService()
    diff1 = service.diff_recipes(old_recipe, new_recipe)
    diff2 = service.diff_recipes(old_recipe, new_recipe)
    assert diff1 == diff2


def test_diff_local_vs_origin_requires_provenance() -> None:
    recipe = _sample_recipe()
    with pytest.raises(ValueError):
        RecipeDiffService().diff_local_vs_origin(recipe)

