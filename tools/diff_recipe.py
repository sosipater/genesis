"""Structured recipe diff CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop.app.bundled_loader import BundledContentLoader
from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.recipe_diff_service import RecipeDiffService


def _load_recipe(path: Path) -> Recipe:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Recipe.from_dict(payload)


def _print(diff: dict, summary: bool) -> None:
    if summary:
        s = diff.get("summary", {})
        print(
            f"metadata_changed={s.get('metadata_fields_changed', 0)} "
            f"added={s.get('entities_added', 0)} removed={s.get('entities_removed', 0)} "
            f"modified={s.get('entities_modified', 0)} order_changed={s.get('order_changed', False)}"
        )
        return
    print(json.dumps(diff, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true", help="Print compact summary instead of full JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    files_cmd = sub.add_parser("files", help="Diff two recipe JSON files")
    files_cmd.add_argument("--old-file", required=True)
    files_cmd.add_argument("--new-file", required=True)

    bundled_cmd = sub.add_parser("bundled-versions", help="Diff two bundled recipe JSON files")
    bundled_cmd.add_argument("--v1-file", required=True)
    bundled_cmd.add_argument("--v2-file", required=True)

    local_origin_cmd = sub.add_parser("local-vs-origin", help="Diff local fork recipe against bundled origin")
    local_origin_cmd.add_argument("--db-path", default=str(ROOT / "desktop" / "data" / "recipe_forge.db"))
    local_origin_cmd.add_argument("--recipe-id", required=True)
    local_origin_cmd.add_argument("--project-root", default=str(ROOT))

    args = parser.parse_args()
    diff_service = RecipeDiffService()

    if args.command == "files":
        old_recipe = _load_recipe(Path(args.old_file))
        new_recipe = _load_recipe(Path(args.new_file))
        diff = diff_service.diff_recipes(old_recipe, new_recipe)
        _print(diff, args.summary)
        return 0

    if args.command == "bundled-versions":
        v1 = _load_recipe(Path(args.v1_file))
        v2 = _load_recipe(Path(args.v2_file))
        diff = diff_service.diff_bundled_versions(v1, v2)
        _print(diff, args.summary)
        return 0

    db = Database(Path(args.db_path))
    try:
        repo = RecipeRepository(db.conn)
        local_recipe = repo.get_recipe_by_id(args.recipe_id)
        if local_recipe is None:
            raise ValueError(f"local recipe not found: {args.recipe_id}")
        bundled_loader = BundledContentLoader(Path(args.project_root))
        with_origin = RecipeDiffService(bundled_loader)
        diff = with_origin.diff_local_vs_origin(local_recipe)
        _print(diff, args.summary)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

