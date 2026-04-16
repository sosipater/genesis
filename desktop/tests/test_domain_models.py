import json
from pathlib import Path

from desktop.app.domain.models import Recipe


def test_recipe_roundtrip_from_sample() -> None:
    root = Path(__file__).resolve().parents[2]
    sample = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    recipe = Recipe.from_dict(sample)
    recipe.validate()
    payload = recipe.to_dict()
    assert payload["id"] == sample["id"]
    assert payload["ingredients"][0]["raw_text"] == "8 oz spaghetti"

