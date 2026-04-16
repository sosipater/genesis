"""Validate bundled content manifest and referenced recipe files."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "shared" / "schemas"
BUNDLED_DIR = ROOT / "bundled_content"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest_path = BUNDLED_DIR / "manifest.json"
    manifest = _load_json(manifest_path)

    schema = _load_json(SCHEMA_DIR / "bundled_manifest.schema.json")
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda e: e.path)
    if errors:
        print("[FAIL] bundled manifest schema validation")
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f"  - {location}: {error.message}")
        return 1

    print("[OK] bundled manifest schema validation")
    recipe_schema = _load_json(SCHEMA_DIR / "recipe.schema.json")
    recipe_validator = Draft202012Validator(recipe_schema)
    seen_ids: set[str] = set()
    expected_files: set[str] = set()

    for recipe_entry in manifest["bundled_recipes"]:
        if recipe_entry["id"] in seen_ids:
            print(f"[FAIL] duplicate bundled recipe id: {recipe_entry['id']}")
            return 1
        seen_ids.add(recipe_entry["id"])
        recipe_rel_path = recipe_entry["file"]
        expected_files.add(recipe_rel_path)
        recipe_path = BUNDLED_DIR / recipe_rel_path
        if not recipe_path.exists():
            print(f"[FAIL] missing recipe file: {recipe_rel_path}")
            return 1
        recipe_payload = _load_json(recipe_path)
        errors = sorted(recipe_validator.iter_errors(recipe_payload), key=lambda e: e.path)
        if errors:
            print(f"[FAIL] invalid bundled recipe schema: {recipe_rel_path}")
            for error in errors:
                location = ".".join(str(part) for part in error.path) or "<root>"
                print(f"  - {location}: {error.message}")
            return 1
        if recipe_payload["scope"] != "bundled":
            print(f"[FAIL] bundled recipe scope must be 'bundled': {recipe_rel_path}")
            return 1
        if recipe_payload["id"] != recipe_entry["id"]:
            print(f"[FAIL] bundled recipe id mismatch for {recipe_rel_path}")
            return 1
        if recipe_payload.get("export_bundle_recipe_id") and recipe_payload["export_bundle_recipe_id"] != recipe_entry["id"]:
            print(f"[FAIL] export_bundle_recipe_id mismatch for {recipe_rel_path}")
            return 1
        checksum = _sha256(recipe_path)
        if checksum != recipe_entry["checksum_sha256"]:
            print(f"[FAIL] checksum mismatch: {recipe_rel_path}")
            return 1
        print(f"[OK] {recipe_rel_path} checksum valid")

        ingredient_ids = {item["id"] for item in recipe_payload.get("ingredients", [])}
        equipment_ids = {item["id"] for item in recipe_payload.get("equipment", [])}
        step_ids = {item["id"] for item in recipe_payload.get("steps", [])}
        for link in recipe_payload.get("step_links", []):
            if link["step_id"] not in step_ids:
                print(f"[FAIL] step_link references missing step in {recipe_rel_path}")
                return 1
            if link["target_type"] == "ingredient" and link["target_id"] not in ingredient_ids:
                print(f"[FAIL] step_link references missing ingredient in {recipe_rel_path}")
                return 1
            if link["target_type"] == "equipment" and link["target_id"] not in equipment_ids:
                print(f"[FAIL] step_link references missing equipment in {recipe_rel_path}")
                return 1

    recipe_files = {f"recipes/{path.name}" for path in (BUNDLED_DIR / "recipes").glob("*.json")}
    orphaned = sorted(recipe_files - expected_files)
    if orphaned:
        print("[FAIL] orphaned bundled recipe files not in manifest:")
        for path in orphaned:
            print(f"  - {path}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

