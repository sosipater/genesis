"""Validate shared sample payloads against JSON schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "shared" / "schemas"
SAMPLE_DIR = ROOT / "shared" / "samples"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _validate(schema_name: str, sample_name: str) -> None:
    schema_path = SCHEMA_DIR / schema_name
    sample_path = SAMPLE_DIR / sample_name
    schema = _load_json(schema_path)
    payload = _load_json(sample_path)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if errors:
      print(f"[FAIL] {sample_name} -> {schema_name}")
      for error in errors:
          location = ".".join(str(part) for part in error.path) or "<root>"
          print(f"  - {location}: {error.message}")
      raise SystemExit(1)

    print(f"[OK] {sample_name} -> {schema_name}")


def main() -> int:
    checks = [
        ("recipe.schema.json", "sample_recipe.json"),
        ("sync_envelope.schema.json", "sample_sync_envelope.json"),
        ("app_config.schema.json", "../contracts/app_config.default.json"),
    ]
    for schema_name, sample_name in checks:
        _validate(schema_name, sample_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

