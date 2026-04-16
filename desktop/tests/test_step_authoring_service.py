import json
from pathlib import Path

import pytest

from desktop.app.domain.models import Recipe
from desktop.app.services.step_authoring_service import StepAuthoringService


def _sample_recipe() -> Recipe:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    return Recipe.from_dict(payload)


def test_link_add_update_remove_and_token_sync() -> None:
    recipe = _sample_recipe()
    service = StepAuthoringService()
    step = recipe.steps[0]
    ingredient = recipe.ingredients[0]

    link = service.add_link(
        recipe,
        step.id,
        "ingredient",
        ingredient.id,
        token_key="salt2",
        label_snapshot=ingredient.raw_text,
        label_override=None,
    )
    assert any(item.id == link.id for item in recipe.step_links)
    assert "[[ingredient:salt2]]" in step.body_text

    service.update_link(recipe, link.id, token_key="salt3", label_override="Kosher salt")
    assert "[[ingredient:salt3]]" in step.body_text
    assert "[[ingredient:salt2]]" not in step.body_text

    service.remove_link(recipe, link.id)
    assert all(item.id != link.id for item in recipe.step_links)
    assert "[[ingredient:salt3]]" not in step.body_text


def test_timer_add_update_remove_validation() -> None:
    recipe = _sample_recipe()
    service = StepAuthoringService()
    step = recipe.steps[0]

    timer = service.add_timer(step, label="Rest", duration_seconds=30, auto_start=False, alert_sound_key=None)
    assert any(item.id == timer.id for item in step.timers)

    service.update_timer(step, timer.id, label="Resting", duration_seconds=45, auto_start=True, alert_sound_key="beep")
    edited = next(item for item in step.timers if item.id == timer.id)
    assert edited.label == "Resting"
    assert edited.duration_seconds == 45
    assert edited.auto_start is True
    assert edited.alert_sound_key == "beep"

    service.remove_timer(step, timer.id)
    assert all(item.id != timer.id for item in step.timers)

    with pytest.raises(ValueError):
        service.add_timer(step, label="x", duration_seconds=0, auto_start=False, alert_sound_key=None)

