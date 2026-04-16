import json
from pathlib import Path

from desktop.app.domain.linking import link_target_exists, resolve_step_link_label
from desktop.app.domain.models import Recipe


def test_link_resolution_and_fallback() -> None:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    recipe = Recipe.from_dict(payload)
    link = recipe.step_links[0]

    assert link_target_exists(recipe, link) is True
    assert resolve_step_link_label(recipe, link) == "spaghetti"

    link.target_id = "123e4567-e89b-12d3-a456-426614174999"
    assert link_target_exists(recipe, link) is False
    assert resolve_step_link_label(recipe, link) == "spaghetti"

