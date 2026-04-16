"""Read-only bundled content loader."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from desktop.app.domain.models import Recipe


class BundledContentLoader:
    def __init__(self, root: Path):
        self._root = root
        schema_dir = self._root / "shared" / "schemas"
        self._manifest_schema = json.loads((schema_dir / "bundled_manifest.schema.json").read_text(encoding="utf-8"))
        self._recipe_schema = json.loads((schema_dir / "recipe.schema.json").read_text(encoding="utf-8"))
        self._bundled_root = self._root / "bundled_content"

    def load_manifest(self) -> dict:
        manifest = json.loads((self._bundled_root / "manifest.json").read_text(encoding="utf-8"))
        Draft202012Validator(self._manifest_schema).validate(manifest)
        return manifest

    def load_bundled_recipes(self) -> list[Recipe]:
        manifest = self.load_manifest()
        recipes: list[Recipe] = []
        validator = Draft202012Validator(self._recipe_schema)
        for entry in manifest["bundled_recipes"]:
            recipe_path = self._bundled_root / entry["file"]
            payload = json.loads(recipe_path.read_text(encoding="utf-8"))
            validator.validate(payload)
            recipe = Recipe.from_dict(payload)
            if recipe.scope != "bundled":
                raise ValueError(f"Bundled recipe {recipe.id} must have scope=bundled")
            recipes.append(recipe)
        return recipes

