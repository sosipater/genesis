"""Import portable recipe share package into local library."""

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
    parser.add_argument("--input", required=True, help="Input share package path")
    parser.add_argument("--source-label", default=None, help="Optional import source label")
    parser.add_argument("--db-path", default=str(ROOT / "desktop" / "data" / "genesis.db"), help="SQLite DB path")
    args = parser.parse_args()

    database = Database(Path(args.db_path))
    try:
        repository = RecipeRepository(database.conn)
        loader = BundledContentLoader(ROOT / "bundled_content")
        service = EditorService(repository, loader, ROOT)
        result = service.import_recipe_share(Path(args.input), args.source_label)
        print(
            f"Imported={result.imported_count} skipped={result.skipped_count} "
            f"collisions={len(result.collisions)} errors={len(result.errors)}"
        )
        if result.collisions:
            print("Collisions:")
            for line in result.collisions:
                print(f"- {line}")
        if result.errors:
            print("Errors:")
            for line in result.errors:
                print(f"- {line}")
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
