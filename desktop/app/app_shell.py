"""Desktop app shell bootstrap wiring services and UI."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from desktop.app.bundled_loader import BundledContentLoader
from desktop.app.config import load_app_config
from desktop.app.logging_setup import configure_logging
from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.runtime_paths import build_runtime_paths
from desktop.app.services.editor_service import EditorService
from desktop.app.ui.windows.main_window import MainWindow


def run_desktop_app(root: Path) -> int:
    config = load_app_config(root)
    runtime_paths = build_runtime_paths(root)
    configure_logging(
        log_level=config.logging["level"],
        enable_file_logging=config.logging["file_enabled"],
        logs_dir=runtime_paths.logs_dir,
    )
    logging.getLogger("genesis.startup").info("Desktop authoring app starting", extra={"subsystem": "startup"})

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(
        """
        QWidget { background-color: #1f1f23; color: #e6e6e6; }
        QLineEdit, QPlainTextEdit, QTableWidget, QListWidget, QTabWidget::pane { background-color: #2a2a2f; color: #e6e6e6; border: 1px solid #444; }
        QPushButton { background-color: #3a3f4b; border: 1px solid #555; padding: 6px; }
        QPushButton:disabled { color: #777; background-color: #2f3238; }
        """
    )

    database = Database(runtime_paths.db_path)
    repository = RecipeRepository(database.conn)
    bundled_loader = BundledContentLoader(root)
    editor_service = EditorService(
        repository,
        bundled_loader,
        root,
        runtime_paths=runtime_paths,
        schema_version=database.schema_version,
        sync_protocol_version=config.sync["protocol_version"],
    )
    window = MainWindow(editor_service)
    window.show()
    return app.exec()

