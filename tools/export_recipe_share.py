"""Export local recipes into a portable share package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop.app.bundled_loader import BundledContentLoader
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.editor_service import EditorService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe-id", action="append", required=True, help="Local recipe ID to export (repeatable)")
    parser.add_argument("--output", required=True, help="Output package path")
    parser.add_argument("--db-path", default=str(ROOT / "desktop" / "data" / "genesis.db"), help="SQLite DB path")
    args = parser.parse_args()

    database = Database(Path(args.db_path))
    try:
        repository = RecipeRepository(database.conn)
        loader = BundledContentLoader(ROOT / "bundled_content")
        service = EditorService(repository, loader, ROOT)
        result = service.export_recipe_share(args.recipe_id, Path(args.output))
        print(f"Exported {result.recipe_count} recipes to {result.package_path} (package {result.package_id})")
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
