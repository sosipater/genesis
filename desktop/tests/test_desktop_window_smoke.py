import json
import os
from pathlib import Path

import pytest


pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.app.domain.models import Recipe
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.editor_service import EditorService
from desktop.app.ui.windows.main_window import MainWindow


class FakeBundledLoader:
    def load_bundled_recipes(self) -> list[Recipe]:
        return []


def test_main_window_smoke(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "ui.db")
    try:
        root = Path(__file__).resolve().parents[2]
        payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
        recipe = Recipe.from_dict(payload)
        repo = RecipeRepository(db.conn)
        repo.create_recipe(recipe)
        service = EditorService(repo, FakeBundledLoader(), root)
        window = MainWindow(service)
        assert window.windowTitle().startswith("Recipe Forge")
        window.close()
    finally:
        db.close()

