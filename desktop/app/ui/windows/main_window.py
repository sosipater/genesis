"""Main desktop authoring window."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.app.domain.models import Recipe
from desktop.app.services.editor_service import EditorService
from desktop.app.services.recipe_search_service import RecipeSearchFilters
from desktop.app.ui.panels.equipment_panel import EquipmentPanel
from desktop.app.ui.panels.ingredients_panel import IngredientsPanel
from desktop.app.ui.panels.library_panel import LibraryPanel
from desktop.app.ui.panels.metadata_panel import MetadataPanel
from desktop.app.ui.panels.steps_panel import StepsPanel
from desktop.app.viewmodels.editor_state import EditorState
from desktop.app.versioning import APP_ID, APP_VERSION, RECIPE_SHARE_FORMAT_VERSION, SYNC_PROTOCOL_VERSION


RecipeSource = Literal["local", "bundled"]


class MainWindow(QMainWindow):
    def __init__(self, editor_service: EditorService):
        super().__init__()
        self._editor_service = editor_service
        self._state = EditorState()
        self._current_recipe: Recipe | None = None
        self._current_grocery_list_id: str | None = None
        self.setWindowTitle(f"Genesis - Desktop Authoring v{APP_VERSION}")
        self.resize(1500, 900)
        self._build_ui()
        self._wire_signals()
        self._refresh_library()
        self._update_status_labels()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        splitter = QSplitter(self)
        outer.addWidget(splitter)

        self.library_panel = LibraryPanel(self)
        splitter.addWidget(self.library_panel)

        center = QWidget(self)
        center_layout = QVBoxLayout(center)
        self.scope_label = QLabel("No recipe selected", center)
        self.dirty_label = QLabel("Clean", center)
        self.save_button = QPushButton("Save", center)
        self.export_bundle_button = QPushButton("Export Bundled Content", center)
        self.home_overview_button = QPushButton("Home", center)
        self.compare_origin_button = QPushButton("Compare With Origin", center)
        self.create_meal_plan_button = QPushButton("Create Meal Plan", center)
        self.add_to_meal_plan_button = QPushButton("Add To Meal Plan", center)
        self.schedule_meal_item_button = QPushButton("Schedule Meal Item", center)
        self.delete_meal_plan_button = QPushButton("Delete Meal Plan", center)
        self.generate_grocery_button = QPushButton("Generate Grocery", center)
        self.generate_week_grocery_button = QPushButton("Grocery This Week", center)
        self.generate_range_grocery_button = QPushButton("Grocery Date Range", center)
        self.view_grocery_button = QPushButton("View Grocery", center)
        self.view_schedule_button = QPushButton("View Schedule", center)
        self.attach_cover_button = QPushButton("Attach Cover", center)
        self.remove_cover_button = QPushButton("Remove Cover", center)
        self.attach_step_image_button = QPushButton("Attach Step Image", center)
        self.remove_step_image_button = QPushButton("Remove Step Image", center)
        self.add_manual_grocery_button = QPushButton("Add Grocery Item", center)
        self.favorite_button = QPushButton("Toggle Favorite", center)
        self.mark_cooked_button = QPushButton("Mark Cooked", center)
        self.export_share_button = QPushButton("Export Share", center)
        self.import_share_button = QPushButton("Import Share", center)
        self.backup_button = QPushButton("Create Backup", center)
        self.restore_button = QPushButton("Restore Backup", center)
        self.media_health_button = QPushButton("Media Health", center)
        self.diagnostics_button = QPushButton("Diagnostics", center)
        self.about_button = QPushButton("About", center)
        self.save_button.setEnabled(False)

        header = QHBoxLayout()
        header.addWidget(self.scope_label)
        header.addWidget(self.dirty_label)
        header.addStretch()
        header.addWidget(self.export_bundle_button)
        header.addWidget(self.home_overview_button)
        header.addWidget(self.compare_origin_button)
        header.addWidget(self.create_meal_plan_button)
        header.addWidget(self.add_to_meal_plan_button)
        header.addWidget(self.schedule_meal_item_button)
        header.addWidget(self.delete_meal_plan_button)
        header.addWidget(self.generate_grocery_button)
        header.addWidget(self.generate_week_grocery_button)
        header.addWidget(self.generate_range_grocery_button)
        header.addWidget(self.view_grocery_button)
        header.addWidget(self.view_schedule_button)
        header.addWidget(self.attach_cover_button)
        header.addWidget(self.remove_cover_button)
        header.addWidget(self.attach_step_image_button)
        header.addWidget(self.remove_step_image_button)
        header.addWidget(self.add_manual_grocery_button)
        header.addWidget(self.favorite_button)
        header.addWidget(self.mark_cooked_button)
        header.addWidget(self.export_share_button)
        header.addWidget(self.import_share_button)
        header.addWidget(self.backup_button)
        header.addWidget(self.restore_button)
        header.addWidget(self.media_health_button)
        header.addWidget(self.diagnostics_button)
        header.addWidget(self.about_button)
        header.addWidget(self.save_button)
        center_layout.addLayout(header)

        self.section_tabs = QTabWidget(center)
        self.equipment_panel = EquipmentPanel(self._editor_service, center)
        self.ingredients_panel = IngredientsPanel(center)
        self.steps_panel = StepsPanel(self._editor_service, center)
        self.section_tabs.addTab(self.equipment_panel, "Equipment")
        self.section_tabs.addTab(self.ingredients_panel, "Ingredients")
        self.section_tabs.addTab(self.steps_panel, "Steps")
        center_layout.addWidget(self.section_tabs)
        splitter.addWidget(center)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        self.metadata_panel = MetadataPanel(right)
        right_layout.addWidget(self.metadata_panel)
        splitter.addWidget(right)
        splitter.setSizes([300, 800, 400])

    def _wire_signals(self) -> None:
        self.library_panel.recipe_selected.connect(self._on_recipe_selected)
        self.library_panel.create_new_requested.connect(self._on_create_new_recipe)
        self.library_panel.duplicate_requested.connect(self._on_duplicate_bundled)
        self.library_panel.search_changed.connect(self._on_search_changed)
        self.library_panel.create_collection_requested.connect(self._on_create_collection)
        self.library_panel.rename_collection_requested.connect(self._on_rename_collection)
        self.library_panel.delete_collection_requested.connect(self._on_delete_collection)
        self.library_panel.view_collection_requested.connect(self._on_view_collection)
        self.library_panel.add_selected_to_collection_requested.connect(self._on_add_selected_to_collection)
        self.library_panel.add_selected_to_working_set_requested.connect(self._on_add_selected_to_working_set)
        self.library_panel.remove_selected_from_working_set_requested.connect(self._on_remove_selected_from_working_set)
        self.library_panel.view_working_set_requested.connect(self._on_view_working_set)
        self.library_panel.view_favorites_requested.connect(self._on_view_favorites)
        self.library_panel.view_recent_opened_requested.connect(self._on_view_recent_opened)
        self.library_panel.view_recent_cooked_requested.connect(self._on_view_recent_cooked)
        self.save_button.clicked.connect(self._on_save)
        self.export_bundle_button.clicked.connect(self._on_export_bundled)
        self.home_overview_button.clicked.connect(self._on_home_overview)
        self.compare_origin_button.clicked.connect(self._on_compare_origin)
        self.create_meal_plan_button.clicked.connect(self._on_create_meal_plan)
        self.add_to_meal_plan_button.clicked.connect(self._on_add_to_meal_plan)
        self.schedule_meal_item_button.clicked.connect(self._on_schedule_meal_item)
        self.delete_meal_plan_button.clicked.connect(self._on_delete_meal_plan_with_undo)
        self.generate_grocery_button.clicked.connect(self._on_generate_grocery)
        self.generate_week_grocery_button.clicked.connect(self._on_generate_grocery_week)
        self.generate_range_grocery_button.clicked.connect(self._on_generate_grocery_range)
        self.view_grocery_button.clicked.connect(self._on_view_grocery)
        self.view_schedule_button.clicked.connect(self._on_view_schedule)
        self.attach_cover_button.clicked.connect(self._on_attach_cover)
        self.remove_cover_button.clicked.connect(self._on_remove_cover)
        self.attach_step_image_button.clicked.connect(self._on_attach_step_image)
        self.remove_step_image_button.clicked.connect(self._on_remove_step_image)
        self.add_manual_grocery_button.clicked.connect(self._on_add_manual_grocery_item)
        self.favorite_button.clicked.connect(self._on_toggle_favorite)
        self.mark_cooked_button.clicked.connect(self._on_mark_cooked)
        self.export_share_button.clicked.connect(self._on_export_share)
        self.import_share_button.clicked.connect(self._on_import_share)
        self.backup_button.clicked.connect(self._on_create_backup)
        self.restore_button.clicked.connect(self._on_restore_backup)
        self.media_health_button.clicked.connect(self._on_media_health)
        self.diagnostics_button.clicked.connect(self._on_diagnostics)
        self.about_button.clicked.connect(self._on_about)

        self.metadata_panel.data_changed.connect(self._mark_dirty)
        self.equipment_panel.data_changed.connect(self._mark_dirty)
        self.ingredients_panel.data_changed.connect(self._mark_dirty)
        self.steps_panel.data_changed.connect(self._mark_dirty)

    def _refresh_library(self) -> None:
        tags = self._editor_service.list_tag_names()
        self.library_panel.set_tag_filter_options(tags)
        self.metadata_panel.set_available_tags(tags)
        self.library_panel.set_items(self._editor_service.list_library_items())
        self.library_panel.set_collections(self._editor_service.list_collections())

    def _on_search_changed(self, query: str, scope: str, tag_filters: list | None = None) -> None:
        filters = RecipeSearchFilters(
            scope=None if scope == "all" else scope,
            tags=list(tag_filters) if tag_filters else None,
        )
        self.library_panel.set_items(self._editor_service.search_library(query, filters))

    def _on_recipe_selected(self, recipe_id: str, source: str) -> None:
        if not self._ensure_safe_to_switch():
            return
        recipe, read_only = self._editor_service.load_recipe(recipe_id, source=source)
        if recipe is None:
            QMessageBox.warning(self, "Recipe Missing", f"Recipe {recipe_id} not found.")
            return
        self._open_recipe(recipe, source=source, read_only=read_only)

    def _on_create_new_recipe(self) -> None:
        if not self._ensure_safe_to_switch():
            return
        recipe = self._editor_service.create_new_local_recipe()
        self._open_recipe(recipe, source="local", read_only=False)
        self._state.mark_dirty()
        self._update_status_labels()

    def _on_duplicate_bundled(self, recipe_id: str) -> None:
        if not self._ensure_safe_to_switch():
            return
        duplicated = self._editor_service.duplicate_bundled_to_local(recipe_id)
        self._open_recipe(duplicated, source="local", read_only=False)
        self._state.mark_dirty()
        self._update_status_labels()

    def _on_save(self) -> None:
        if self._current_recipe is None or self._state.is_read_only:
            return
        self._sync_panels_to_recipe()
        try:
            self._editor_service.save_recipe(self._current_recipe)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return
        self._state.mark_clean()
        self._update_status_labels()
        self._refresh_library()

    def _on_export_bundled(self) -> None:
        content_version, ok = QInputDialog.getText(self, "Export Bundled Content", "App Content Version", text="0.1.0")
        if not ok:
            return
        try:
            result = self._editor_service.export_eligible_bundled_content(content_version.strip())
        except Exception as exc:
            QMessageBox.critical(self, "Bundle Export Failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Bundle Export Complete",
            (
                f"Exported {result.exported_count} recipes\nManifest: {result.manifest_path}\n"
                + (f"\nWarnings:\n- " + "\n- ".join(result.warnings) if result.warnings else "")
            ),
        )
        self._refresh_library()

    def _on_home_overview(self) -> None:
        overview = self._editor_service.get_home_overview()
        lines: list[str] = []
        lines.append("Today:")
        if overview.today:
            for item in overview.today:
                slot = item.slot_label if item.meal_slot == "custom" else (item.meal_slot or "unslotted")
                lines.append(f"- [{slot}] {item.recipe_title} ({item.meal_plan_name})")
        else:
            lines.append("- No meals scheduled today")
        lines.append("")
        lines.append("This Week:")
        if overview.this_week:
            for day, entries in overview.this_week.items():
                lines.append(f"{day}:")
                for item in entries:
                    slot = item.slot_label if item.meal_slot == "custom" else (item.meal_slot or "unslotted")
                    lines.append(f"  - [{slot}] {item.recipe_title}")
        else:
            lines.append("- No meals scheduled this week")
        lines.append("")
        lines.append("Quick Resume:")
        lines.append(f"- Recent recipe: {overview.quick_recent_recipe_title or 'None'}")
        lines.append(f"- Latest grocery: {overview.quick_latest_grocery_name or 'None'}")
        lines.append(f"- Active meal plan: {overview.quick_active_meal_plan_name or 'None'}")
        QMessageBox.information(self, "Home Overview", "\n".join(lines))

    def _on_compare_origin(self) -> None:
        if self._current_recipe is None:
            return
        if not self._current_recipe.is_forked_from_bundled:
            QMessageBox.information(self, "Compare With Origin", "Current recipe is not a bundled fork.")
            return
        self._sync_panels_to_recipe()
        try:
            diff = self._editor_service.compare_local_with_origin(self._current_recipe)
        except Exception as exc:
            QMessageBox.warning(self, "Compare Failed", str(exc))
            return
        summary = diff.get("summary", {})
        detail = json.dumps(diff, indent=2)
        QMessageBox.information(
            self,
            "Origin Diff Summary",
            (
                f"Metadata fields changed: {summary.get('metadata_fields_changed', 0)}\n"
                f"Entities added: {summary.get('entities_added', 0)}\n"
                f"Entities removed: {summary.get('entities_removed', 0)}\n"
                f"Entities modified: {summary.get('entities_modified', 0)}\n"
                f"Order changed: {summary.get('order_changed', False)}\n\n"
                f"Structured Diff:\n{detail}"
            ),
        )

    def _on_create_collection(self) -> None:
        name, ok = QInputDialog.getText(self, "Create Collection", "Collection name")
        if not ok or not name.strip():
            return
        self._editor_service.create_collection(name.strip())
        self._refresh_library()

    def _on_rename_collection(self, collection_id: str) -> None:
        name, ok = QInputDialog.getText(self, "Rename Collection", "Collection name")
        if not ok or not name.strip():
            return
        self._editor_service.rename_collection(collection_id, name.strip())
        self._refresh_library()

    def _on_delete_collection(self, collection_id: str) -> None:
        self._editor_service.delete_collection(collection_id)
        self._refresh_library()

    def _on_view_collection(self, collection_id: str) -> None:
        recipes = self._editor_service.list_collection_recipes(collection_id)
        self.library_panel.set_items(
            [
                item
                for item in self._editor_service.list_library_items()
                if any(recipe.id == item.id for recipe in recipes)
            ]
        )

    def _on_add_selected_to_collection(self, collection_id: str) -> None:
        if self._current_recipe is None:
            return
        self._editor_service.add_recipe_to_collection(collection_id, self._current_recipe.id)
        self._refresh_library()

    def _on_add_selected_to_working_set(self) -> None:
        if self._current_recipe is None:
            return
        self._editor_service.add_recipe_to_working_set(self._current_recipe.id)
        QMessageBox.information(self, "Working Set", "Recipe added to working set.")

    def _on_remove_selected_from_working_set(self) -> None:
        if self._current_recipe is None:
            return
        self._editor_service.remove_recipe_from_working_set(self._current_recipe.id)
        QMessageBox.information(self, "Working Set", "Recipe removed from working set.")

    def _on_view_working_set(self) -> None:
        recipes = self._editor_service.list_working_set_recipes()
        self.library_panel.set_items(
            [
                item
                for item in self._editor_service.list_library_items()
                if any(recipe.id == item.id for recipe in recipes)
            ]
        )

    def _on_view_favorites(self) -> None:
        recipes = self._editor_service.list_favorite_recipes()
        self.library_panel.set_items([item for item in self._editor_service.list_library_items() if any(r.id == item.id for r in recipes)])

    def _on_view_recent_opened(self) -> None:
        recipes = self._editor_service.list_recent_opened_recipes()
        self.library_panel.set_items([item for item in self._editor_service.list_library_items() if any(r.id == item.id for r in recipes)])

    def _on_view_recent_cooked(self) -> None:
        recipes = self._editor_service.list_recent_cooked_recipes()
        self.library_panel.set_items([item for item in self._editor_service.list_library_items() if any(r.id == item.id for r in recipes)])

    def _on_create_meal_plan(self) -> None:
        name, ok = QInputDialog.getText(self, "Create Meal Plan", "Meal plan name")
        if not ok or not name.strip():
            return
        self._editor_service.create_meal_plan(name.strip())
        QMessageBox.information(self, "Meal Plan", "Meal plan created.")

    def _on_add_to_meal_plan(self) -> None:
        if self._current_recipe is None:
            return
        plans = self._editor_service.list_meal_plans()
        if not plans:
            QMessageBox.information(self, "Meal Plan", "Create a meal plan first.")
            return
        names = [f"{item['name']} ({item['id']})" for item in plans]
        chosen, ok = QInputDialog.getItem(self, "Add To Meal Plan", "Select meal plan", names, editable=False)
        if not ok:
            return
        selected_id = chosen.split("(")[-1].rstrip(")")
        servings, ok2 = QInputDialog.getDouble(
            self,
            "Servings Override",
            "Override servings (0 = recipe default)",
            value=0.0,
            minValue=0.0,
            decimals=2,
        )
        if not ok2:
            return
        self._editor_service.add_meal_plan_item(
            selected_id, self._current_recipe.id, servings_override=(None if servings <= 0 else servings)
        )
        QMessageBox.information(self, "Meal Plan", "Recipe added to meal plan.")

    def _on_schedule_meal_item(self) -> None:
        if self._current_recipe is None:
            return
        plans = self._editor_service.list_meal_plans()
        if not plans:
            QMessageBox.information(self, "Meal Plan", "Create a meal plan first.")
            return
        names = [f"{item['name']} ({item['id']})" for item in plans]
        chosen, ok = QInputDialog.getItem(self, "Schedule Meal", "Select meal plan", names, editable=False)
        if not ok:
            return
        selected_id = chosen.split("(")[-1].rstrip(")")
        planned_date, ok_date = QInputDialog.getText(self, "Planned Date", "YYYY-MM-DD")
        if not ok_date:
            return
        meal_slot, ok_slot = QInputDialog.getItem(
            self, "Meal Slot", "Slot", ["breakfast", "lunch", "dinner", "snack", "custom"], editable=False
        )
        if not ok_slot:
            return
        slot_label = None
        if meal_slot == "custom":
            slot_label, ok_label = QInputDialog.getText(self, "Custom Slot Label", "Label")
            if not ok_label:
                return
        self._editor_service.add_meal_plan_item(
            selected_id,
            self._current_recipe.id,
            planned_date=(planned_date.strip() or None),
            meal_slot=meal_slot,
            slot_label=(slot_label.strip() if slot_label else None),
        )
        QMessageBox.information(self, "Meal Plan", "Recipe scheduled.")

    def _on_delete_meal_plan_with_undo(self) -> None:
        plans = self._editor_service.list_meal_plans()
        if not plans:
            QMessageBox.information(self, "Meal Plan", "No meal plans available.")
            return
        names = [f"{item['name']} ({item['id']})" for item in plans]
        chosen, ok = QInputDialog.getItem(self, "Delete Meal Plan", "Select meal plan", names, editable=False)
        if not ok:
            return
        selected_id = chosen.split("(")[-1].rstrip(")")
        self._editor_service.delete_meal_plan(selected_id)
        undo = QMessageBox.question(
            self,
            "Meal Plan Deleted",
            "Meal plan deleted. Undo?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if undo == QMessageBox.Yes:
            self._editor_service.restore_meal_plan(selected_id)
            QMessageBox.information(self, "Meal Plan", "Deletion undone.")

    def _on_generate_grocery(self) -> None:
        plans = self._editor_service.list_meal_plans()
        if not plans:
            QMessageBox.information(self, "Grocery", "Create a meal plan first.")
            return
        names = [f"{item['name']} ({item['id']})" for item in plans]
        chosen, ok = QInputDialog.getItem(self, "Generate Grocery", "Select meal plan", names, editable=False)
        if not ok:
            return
        selected_id = chosen.split("(")[-1].rstrip(")")
        grocery_id = self._editor_service.regenerate_grocery_list_snapshot(selected_id)
        self._current_grocery_list_id = grocery_id
        items = self._editor_service.list_grocery_list_items(grocery_id)
        lines = []
        for item in items:
            qty = "" if item["quantity_value"] is None else str(item["quantity_value"])
            unit = item["unit"] or ""
            lines.append(f"- {item['name']} {qty} {unit}".strip())
        QMessageBox.information(self, "Grocery List", "\n".join(lines) if lines else "No items generated.")

    def _on_generate_grocery_week(self) -> None:
        plans = self._editor_service.list_meal_plans()
        if not plans:
            QMessageBox.information(self, "Grocery", "Create a meal plan first.")
            return
        names = [f"{item['name']} ({item['id']})" for item in plans]
        chosen, ok = QInputDialog.getItem(self, "Generate Weekly Grocery", "Select meal plan", names, editable=False)
        if not ok:
            return
        selected_id = chosen.split("(")[-1].rstrip(")")
        week_start, ok_date = QInputDialog.getText(self, "Week Start", "Week start date (YYYY-MM-DD)")
        if not ok_date or not week_start.strip():
            return
        grocery_id = self._editor_service.generate_weekly_grocery_snapshot(selected_id, week_start.strip())
        self._current_grocery_list_id = grocery_id
        QMessageBox.information(self, "Grocery", "Weekly grocery snapshot generated.")

    def _on_generate_grocery_range(self) -> None:
        plans = self._editor_service.list_meal_plans()
        if not plans:
            QMessageBox.information(self, "Grocery", "Create a meal plan first.")
            return
        names = [f"{item['name']} ({item['id']})" for item in plans]
        chosen, ok = QInputDialog.getItem(self, "Generate Grocery Range", "Select meal plan", names, editable=False)
        if not ok:
            return
        selected_id = chosen.split("(")[-1].rstrip(")")
        start_date, ok_start = QInputDialog.getText(self, "Start Date", "Start YYYY-MM-DD")
        if not ok_start:
            return
        end_date, ok_end = QInputDialog.getText(self, "End Date", "End YYYY-MM-DD")
        if not ok_end:
            return
        grocery_id = self._editor_service.generate_grocery_list_from_meal_plan(
            selected_id,
            start_date=(start_date.strip() or None),
            end_date=(end_date.strip() or None),
        )
        self._current_grocery_list_id = grocery_id
        QMessageBox.information(self, "Grocery", "Date-range grocery snapshot generated.")

    def _on_view_grocery(self) -> None:
        if self._current_grocery_list_id is None:
            lists = self._editor_service.list_grocery_lists()
            if not lists:
                QMessageBox.information(self, "Grocery", "No grocery lists available.")
                return
            self._current_grocery_list_id = lists[0]["id"]
        items = self._editor_service.list_grocery_list_items(self._current_grocery_list_id)
        lines = []
        for item in items:
            marker = "[x]" if item["checked"] else "[ ]"
            source = item.get("source_type", "generated")
            qty = "" if item["quantity_value"] is None else str(item["quantity_value"])
            unit = item["unit"] or ""
            lines.append(f"{marker} {item['name']} {qty} {unit} ({source})".strip())
        QMessageBox.information(self, "Grocery Items", "\n".join(lines) if lines else "No items.")

    def _on_view_schedule(self) -> None:
        plans = self._editor_service.list_meal_plans()
        if not plans:
            QMessageBox.information(self, "Schedule", "No meal plans available.")
            return
        names = [f"{item['name']} ({item['id']})" for item in plans]
        chosen, ok = QInputDialog.getItem(self, "View Schedule", "Select meal plan", names, editable=False)
        if not ok:
            return
        selected_id = chosen.split("(")[-1].rstrip(")")
        grouped = self._editor_service.list_meal_plan_items_grouped_by_date(selected_id)
        recipe_map = {item.id: item.title for item in self._editor_service.list_library_items()}
        lines: list[str] = []
        for date_key, items in grouped.items():
            lines.append(f"{date_key}:")
            for row in items:
                slot = row.get("meal_slot") or "unslotted"
                if slot == "custom" and row.get("slot_label"):
                    slot = row["slot_label"]
                lines.append(f"  - [{slot}] {recipe_map.get(row['recipe_id'], row['recipe_id'])}")
            lines.append("")
        QMessageBox.information(self, "Meal Schedule", "\n".join(lines) if lines else "No scheduled items.")

    def _on_attach_cover(self) -> None:
        if self._current_recipe is None or self._state.is_read_only:
            return
        source, ok = QInputDialog.getText(self, "Attach Cover Image", "Image file path")
        if not ok or not source.strip():
            return
        try:
            self._editor_service.attach_cover_media(self._current_recipe, Path(source.strip()))
        except Exception as exc:
            QMessageBox.warning(self, "Attach Cover Failed", str(exc))
            return
        self._state.mark_dirty()
        self._update_status_labels()
        QMessageBox.information(self, "Cover Image", "Cover image attached.")

    def _on_remove_cover(self) -> None:
        if self._current_recipe is None or self._state.is_read_only:
            return
        self._editor_service.remove_cover_media(self._current_recipe)
        self._state.mark_dirty()
        self._update_status_labels()
        QMessageBox.information(self, "Cover Image", "Cover image removed.")

    def _on_attach_step_image(self) -> None:
        if self._current_recipe is None or self._state.is_read_only:
            return
        if not self._current_recipe.steps:
            QMessageBox.information(self, "Step Image", "No steps available.")
            return
        step_options = [f"{idx + 1}: {(step.title or step.body_text[:40])} ({step.id})" for idx, step in enumerate(self._current_recipe.steps)]
        chosen, ok = QInputDialog.getItem(self, "Attach Step Image", "Select step", step_options, editable=False)
        if not ok:
            return
        step_id = chosen.split("(")[-1].rstrip(")")
        source, ok2 = QInputDialog.getText(self, "Attach Step Image", "Image file path")
        if not ok2 or not source.strip():
            return
        try:
            self._editor_service.attach_step_media(self._current_recipe, step_id, Path(source.strip()))
        except Exception as exc:
            QMessageBox.warning(self, "Attach Step Image Failed", str(exc))
            return
        self._state.mark_dirty()
        self._update_status_labels()
        QMessageBox.information(self, "Step Image", "Step image attached.")

    def _on_remove_step_image(self) -> None:
        if self._current_recipe is None or self._state.is_read_only:
            return
        steps_with_media = [step for step in self._current_recipe.steps if step.media_id]
        if not steps_with_media:
            QMessageBox.information(self, "Step Image", "No step images attached.")
            return
        options = [f"{idx + 1}: {(step.title or step.body_text[:40])} ({step.id})" for idx, step in enumerate(steps_with_media)]
        chosen, ok = QInputDialog.getItem(self, "Remove Step Image", "Select step", options, editable=False)
        if not ok:
            return
        step_id = chosen.split("(")[-1].rstrip(")")
        self._editor_service.remove_step_media(self._current_recipe, step_id)
        self._state.mark_dirty()
        self._update_status_labels()
        QMessageBox.information(self, "Step Image", "Step image removed.")

    def _on_add_manual_grocery_item(self) -> None:
        if self._current_grocery_list_id is None:
            QMessageBox.information(self, "Grocery", "Generate or view a grocery list first.")
            return
        name, ok = QInputDialog.getText(self, "Add Grocery Item", "Item name")
        if not ok or not name.strip():
            return
        qty, ok_qty = QInputDialog.getDouble(
            self,
            "Quantity",
            "Quantity (0 for none)",
            value=0.0,
            minValue=0.0,
            decimals=2,
        )
        if not ok_qty:
            return
        unit, _ = QInputDialog.getText(self, "Unit", "Unit (optional)")
        self._editor_service.add_manual_grocery_item(
            self._current_grocery_list_id,
            name.strip(),
            None if qty <= 0 else qty,
            unit.strip() or None,
        )
        QMessageBox.information(self, "Grocery", "Manual grocery item added.")

    def _on_toggle_favorite(self) -> None:
        if self._current_recipe is None:
            return
        library_map = {item.id: item for item in self._editor_service.list_library_items()}
        is_favorite = bool(library_map.get(self._current_recipe.id, None) and library_map[self._current_recipe.id].is_favorite)
        self._editor_service.set_favorite(self._current_recipe.id, not is_favorite)
        self._refresh_library()

    def _on_mark_cooked(self) -> None:
        if self._current_recipe is None:
            return
        self._editor_service.mark_cooked(self._current_recipe.id)
        self._refresh_library()
        QMessageBox.information(self, "Cooked", "Recipe marked as cooked.")

    def _on_export_share(self) -> None:
        if self._current_recipe is None:
            QMessageBox.information(self, "Export Share", "Select a local recipe first.")
            return
        if self._current_recipe.scope != "local":
            QMessageBox.information(self, "Export Share", "Only local recipes can be shared.")
            return
        path_text, ok = QInputDialog.getText(
            self,
            "Export Recipe Share",
            "Package output path (.json)",
            text="recipe_share_export.json",
        )
        if not ok or not path_text.strip():
            return
        ids_text, ok_ids = QInputDialog.getText(
            self,
            "Recipe IDs",
            "Comma-separated local recipe IDs to export",
            text=self._current_recipe.id,
        )
        if not ok_ids:
            return
        recipe_ids = [value.strip() for value in ids_text.split(",") if value.strip()]
        try:
            result = self._editor_service.export_recipe_share(recipe_ids, Path(path_text.strip()))
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot share this recipe yet", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Export Complete",
            f"Exported {result.recipe_count} recipe(s)\nPackage: {result.package_path}\nPackage ID: {result.package_id}",
        )

    def _on_import_share(self) -> None:
        path_text, ok = QInputDialog.getText(self, "Import Recipe Share", "Package path (.json)")
        if not ok or not path_text.strip():
            return
        result = self._editor_service.import_recipe_share(Path(path_text.strip()))
        QMessageBox.information(
            self,
            "Import Result",
            (
                f"Imported: {result.imported_count}\n"
                f"Skipped: {result.skipped_count}\n"
                f"Collisions: {len(result.collisions)}\n"
                f"Errors: {len(result.errors)}"
                + (f"\n\nCollision Details:\n- " + "\n- ".join(result.collisions) if result.collisions else "")
                + (f"\n\nErrors:\n- " + "\n- ".join(result.errors) if result.errors else "")
            ),
        )
        self._refresh_library()

    def _on_create_backup(self) -> None:
        default_name = f"genesis_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path_text, ok = QInputDialog.getText(
            self,
            "Create Backup",
            "Backup archive path (.zip)",
            text=default_name,
        )
        if not ok or not path_text.strip():
            return
        try:
            result = self._editor_service.create_backup(Path(path_text.strip()))
        except Exception as exc:
            QMessageBox.warning(self, "Backup Failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Backup Complete",
            f"Path: {result['path']}\nFiles: {result['file_count']}\nBytes: {result['total_bytes']}",
        )

    def _on_restore_backup(self) -> None:
        path_text, ok = QInputDialog.getText(self, "Restore Backup", "Backup archive path (.zip)")
        if not ok or not path_text.strip():
            return
        confirm = QMessageBox.question(
            self,
            "Restore Backup",
            "Restore uses full replace semantics and can overwrite local data. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        result = self._editor_service.restore_backup(Path(path_text.strip()), allow_replace=True)
        if result.get("ok"):
            QMessageBox.information(self, "Restore Complete", "Backup restored. Restart the app to reload restored data.")
            return
        QMessageBox.warning(self, "Restore Failed", "\n".join(result.get("errors", ["Unknown restore error"])))

    def _on_media_health(self) -> None:
        report = self._editor_service.media_health_report()
        lines = [
            f"Media root: {report['media_root']}",
            f"Assets: {report['asset_count']}",
            f"Orphan assets: {len(report['orphan_assets'])}",
            f"Missing files: {len(report['missing_files'])}",
            f"Dangling references: {len(report['dangling_references'])}",
        ]
        if report["orphan_assets"]:
            do_cleanup = QMessageBox.question(
                self,
                "Media Health",
                "\n".join(lines) + "\n\nClean up orphan assets now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if do_cleanup == QMessageBox.Yes:
                cleanup = self._editor_service.cleanup_orphan_media(report["orphan_assets"])
                lines.append(f"Removed orphan assets: {cleanup['removed_count']}")
        QMessageBox.information(self, "Media Health", "\n".join(lines))

    def _on_diagnostics(self) -> None:
        QMessageBox.information(self, "Diagnostics", self._editor_service.diagnostics_text())

    def _on_about(self) -> None:
        report = self._editor_service.diagnostics_report()
        QMessageBox.information(
            self,
            "About Genesis",
            (
                f"App: {APP_ID}\n"
                f"Version: {APP_VERSION}\n"
                f"Schema version: {report['version']['schema_version']}\n"
                f"Sync protocol: {SYNC_PROTOCOL_VERSION}\n"
                f"Share format: {RECIPE_SHARE_FORMAT_VERSION}\n"
                "\n"
                "Your library can be backed up anytime from Create Backup in the toolbar."
            ),
        )

    def _open_recipe(self, recipe: Recipe, source: RecipeSource, read_only: bool) -> None:
        self._current_recipe = copy.deepcopy(recipe)
        self._state.open_recipe(recipe.id, scope=source, is_read_only=read_only)
        self.metadata_panel.load_recipe(self._current_recipe)
        self.equipment_panel.load_recipe(self._current_recipe)
        self.ingredients_panel.load_recipe(self._current_recipe)
        self.steps_panel.load_recipe(self._current_recipe)
        self.metadata_panel.set_read_only(read_only)
        self.equipment_panel.set_read_only(read_only)
        self.ingredients_panel.set_read_only(read_only)
        self.steps_panel.set_read_only(read_only)
        self._update_status_labels()

    def _sync_panels_to_recipe(self) -> None:
        if self._current_recipe is None:
            return
        self.metadata_panel.apply_to_recipe(self._current_recipe)
        self.equipment_panel.apply_to_recipe(self._current_recipe)
        self.ingredients_panel.apply_to_recipe(self._current_recipe)
        self.steps_panel.apply_to_recipe(self._current_recipe)

    def _mark_dirty(self) -> None:
        if self._current_recipe is None:
            return
        self._state.mark_dirty()
        self._update_status_labels()

    def _update_status_labels(self) -> None:
        if self._current_recipe is None:
            self.scope_label.setText("No recipe selected")
            self.dirty_label.setText("Clean")
            self.save_button.setEnabled(False)
            self.compare_origin_button.setEnabled(False)
            return
        mode_text = "Bundled Read-Only" if self._state.is_read_only else "Local Editable"
        cover_flag = " [Cover]" if self._current_recipe.cover_media_id else ""
        self.scope_label.setText(f"{mode_text} - {self._current_recipe.title}{cover_flag}")
        self.dirty_label.setText("Unsaved Changes" if self._state.is_dirty else "Saved")
        self.save_button.setEnabled(self._state.can_save)
        self.compare_origin_button.setEnabled(
            self._current_recipe.scope == "local" and bool(self._current_recipe.is_forked_from_bundled)
        )

    def _ensure_safe_to_switch(self) -> bool:
        if not self._state.is_dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Current recipe has unsaved changes. Continue and discard changes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return result == QMessageBox.Yes

