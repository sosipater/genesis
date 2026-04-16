"""Seed starter sample data for local development."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "shared" / "samples"


def main() -> int:
    source = SAMPLES / "sample_recipe.json"
    output = ROOT / "tests" / "fixtures" / "seed_recipe.json"
    recipe = json.loads(source.read_text(encoding="utf-8"))
    output.write_text(json.dumps(recipe, indent=2), encoding="utf-8")
    print(f"Seeded fixture: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

