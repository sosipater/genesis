"""Export local eligible recipes into bundled content package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.bundle_export_service import BundleExportService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content-version", required=True, help="App bundled content version")
    parser.add_argument("--db-path", default=str(ROOT / "desktop" / "data" / "recipe_forge.db"), help="Local sqlite db path")
    args = parser.parse_args()
    database = Database(Path(args.db_path))
    try:
        repository = RecipeRepository(database.conn)
        exporter = BundleExportService(repository, ROOT)
        result = exporter.export_eligible(args.content_version)
        print(f"Exported {result.exported_count} recipes to {result.manifest_path}")
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

