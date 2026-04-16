"""Ingredients section editor supporting raw and structured entry."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.app.domain.models import Recipe, RecipeIngredientItem
from desktop.app.services.editor_service import EditorService
from desktop.app.ui.widgets.list_editor_widget import ListEditorWidget

_ROLE_CATALOG_ID = Qt.ItemDataRole.UserRole + 1
_ROLE_SUB_RECIPE_ID = Qt.ItemDataRole.UserRole + 2
_ROLE_SUB_USAGE = Qt.ItemDataRole.UserRole + 3
_ROLE_SUB_MULT = Qt.ItemDataRole.UserRole + 4
_ROLE_SUB_TITLE = Qt.ItemDataRole.UserRole + 5


class CatalogIngredientPickerDialog(QDialog):
    def __init__(self, editor_service: EditorService, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Ingredient library")
        self._editor_service = editor_service
        self._selected: dict[str, str | None] | None = None

        self._filter = QLineEdit(self)
        self._filter.setPlaceholderText("Search…")
        self._list = QListWidget(self)

        self._new_name = QLineEdit(self)
        self._new_notes = QLineEdit(self)
        create_btn = QPushButton("Create & add to recipe", self)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Pick a catalog item or create a new library entry.", self))
        layout.addWidget(self._filter)
        layout.addWidget(self._list)

        form = QFormLayout()
        form.addRow("New name", self._new_name)
        form.addRow("New notes (optional)", self._new_notes)
        layout.addLayout(form)
        layout.addWidget(create_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close, self)
        buttons.accepted.connect(self._accept_current)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._filter.textChanged.connect(self._refresh_list)
        self._list.itemDoubleClicked.connect(self._accept_current)
        create_btn.clicked.connect(self._create_and_accept)

        self._visible_rows: list[dict[str, str | None]] = []
        self._refresh_list()

    def selected(self) -> dict[str, str | None] | None:
        return self._selected

    def _refresh_list(self) -> None:
        needle = self._filter.text().strip().lower()
        self._list.clear()
        self._visible_rows = []
        for row in self._editor_service.list_catalog_ingredient_summaries():
            notes = row["notes"] or ""
            if needle and needle not in row["name"].lower() and (not notes or needle not in notes.lower()):
                continue
            self._visible_rows.append(row)
            QListWidgetItem(row["name"], self._list)

    def _accept_current(self) -> None:
        row_idx = self._list.currentRow()
        if row_idx < 0 or row_idx >= len(self._visible_rows):
            return
        item = self._visible_rows[row_idx]
        self._selected = {"id": item["id"], "name": item["name"], "notes": item["notes"]}
        self.accept()

    def _create_and_accept(self) -> None:
        name = self._new_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Enter a name for the new catalog ingredient.")
            return
        notes = self._new_notes.text().strip() or None
        try:
            cid = self._editor_service.create_catalog_ingredient_record(name, notes=notes)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot create", str(exc))
            return
        self._selected = {"id": cid, "name": name, "notes": notes}
        self.accept()


class SubRecipePickerDialog(QDialog):
    """Pick another local recipe as a sub-recipe ingredient (explicit usage, no unit conversion)."""

    def __init__(self, editor_service: EditorService, *, exclude_recipe_id: str | None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Use recipe as ingredient")
        self._editor_service = editor_service
        self._exclude_recipe_id = exclude_recipe_id
        self._rows: list[dict[str, str]] = []

        self._recipe_combo = QComboBox(self)
        self._usage_combo = QComboBox(self)
        self._usage_combo.addItem("Full batch (1×)", "full_batch")
        self._usage_combo.addItem("Fraction of batch…", "fraction_of_batch")
        self._mult = QDoubleSpinBox(self)
        self._mult.setMinimum(0.25)
        self._mult.setMaximum(99.0)
        self._mult.setSingleStep(0.25)
        self._mult.setValue(1.0)
        self._mult.setEnabled(False)
        self._usage_combo.currentIndexChanged.connect(self._on_usage_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sub-recipe references expand into that recipe’s ingredients for grocery lists.", self))
        form = QFormLayout()
        form.addRow("Recipe", self._recipe_combo)
        form.addRow("Usage", self._usage_combo)
        form.addRow("Multiplier", self._mult)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._reload_recipes()

    def _on_usage_changed(self) -> None:
        usage = self._usage_combo.currentData()
        self._mult.setEnabled(usage == "fraction_of_batch")

    def _reload_recipes(self) -> None:
        self._recipe_combo.clear()
        self._rows = self._editor_service.list_local_recipes_for_sub_recipe_picker(exclude_recipe_id=self._exclude_recipe_id)
        for row in self._rows:
            self._recipe_combo.addItem(row["title"], row["id"])

    def selected(self) -> dict[str, str | float] | None:
        if self._recipe_combo.count() == 0:
            return None
        idx = self._recipe_combo.currentIndex()
        rid = str(self._recipe_combo.currentData())
        title = self._rows[idx]["title"]
        usage = str(self._usage_combo.currentData())
        mult = float(self._mult.value()) if usage == "fraction_of_batch" else 1.0
        return {"sub_recipe_id": rid, "title": title, "usage": usage, "multiplier": mult}


class IngredientsPanel(ListEditorWidget):
    def __init__(self, editor_service: EditorService, parent: QWidget | None = None):
        self._editor = editor_service
        self._pick_button = QPushButton("Ingredient library…", parent)
        self._pick_button.clicked.connect(self._pick_from_catalog)
        self._sub_button = QPushButton("Use recipe as ingredient…", parent)
        self._sub_button.clicked.connect(self._pick_sub_recipe)
        self._save_pool_button = QPushButton("Save line to library", parent)
        self._save_pool_button.clicked.connect(self._save_selection_to_catalog)

        self._pending_catalog_id: str | None = None
        self._catalog_pick_map: dict[str, str] = {}
        self._current_recipe_id: str | None = None

        super().__init__(
            ["Ingredient line", "Quantity", "Unit", "Name", "Optional (true/false)", "Preparation Notes"],
            parent,
            extra_toolbar_widgets=(self._pick_button, self._sub_button, self._save_pool_button),
        )

        self._quick_input = QLineEdit(self)
        self._quick_input.setPlaceholderText("Type a line, e.g. 2 cups flour — suggestions match your library")
        self._quick_add_button = QPushButton("Add line", self)
        self._quick_add_button.clicked.connect(self._quick_add_row)
        self._quick_input.returnPressed.connect(self._quick_add_row)
        quick_row = QHBoxLayout()
        quick_row.addWidget(self._quick_input, stretch=1)
        quick_row.addWidget(self._quick_add_button)
        root_layout = self.layout()
        assert root_layout is not None
        root_layout.insertLayout(1, quick_row)

        self._completion_model = QStringListModel(self)
        self._completer = QCompleter(self)
        self._completer.setModel(self._completion_model)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setWidget(self._quick_input)
        self._quick_input.textChanged.connect(self._on_quick_text_changed)
        self._completer.activated.connect(self._on_completer_activated)

    def _on_quick_text_changed(self, text: str) -> None:
        t = text.strip()
        if len(t) < 1:
            self._completion_model.setStringList([])
            self._catalog_pick_map.clear()
            return
        hits = self._editor.search_catalog_ingredient_summaries(t, limit=25)
        self._catalog_pick_map = {str(h["name"]): str(h["id"]) for h in hits}
        self._completion_model.setStringList([str(h["name"]) for h in hits])

    def _on_completer_activated(self, text: str) -> None:
        self._pending_catalog_id = self._catalog_pick_map.get(text)

    def _pick_from_catalog(self) -> None:
        dialog = CatalogIngredientPickerDialog(self._editor, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        sel = dialog.selected()
        if not sel:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        line = sel["name"] or ""
        self.table.setItem(row, 0, QTableWidgetItem(line))
        for column in range(1, 4):
            self.table.setItem(row, column, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem("false"))
        self.table.setItem(row, 5, QTableWidgetItem(""))
        id_item = self.table.item(row, 0)
        id_item.setData(Qt.ItemDataRole.UserRole, str(uuid4()))
        id_item.setData(_ROLE_CATALOG_ID, sel["id"])
        for role in (_ROLE_SUB_RECIPE_ID, _ROLE_SUB_USAGE, _ROLE_SUB_MULT, _ROLE_SUB_TITLE):
            id_item.setData(role, None)
        id_item.setToolTip("")
        self.data_changed.emit()

    def _save_selection_to_catalog(self) -> None:
        row = self.table.currentRow()
        text = ""
        if row >= 0 and self.table.item(row, 0):
            text = self.table.item(row, 0).text().strip()
        if not text:
            text = self._quick_input.text().strip()
        if not text:
            QMessageBox.information(self, "Nothing to save", "Select a row or type a line first.")
            return
        name, ok = QInputDialog.getText(self, "Save to ingredient library", "Library name:", text=text)
        if not ok or not name.strip():
            return
        name = name.strip()
        try:
            cid = self._editor.create_catalog_ingredient_record(name)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot create", str(exc))
            return
        if row >= 0 and self.table.item(row, 0):
            id_item = self.table.item(row, 0)
            id_item.setData(_ROLE_CATALOG_ID, cid)
        self.data_changed.emit()

    def _quick_add_row(self) -> None:
        text = self._quick_input.text().strip()
        if not text:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(text))
        for column in range(1, 4):
            self.table.setItem(row, column, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem("false"))
        self.table.setItem(row, 5, QTableWidgetItem(""))
        id_item = self.table.item(row, 0)
        id_item.setData(Qt.ItemDataRole.UserRole, str(uuid4()))
        if self._pending_catalog_id:
            id_item.setData(_ROLE_CATALOG_ID, self._pending_catalog_id)
        for role in (_ROLE_SUB_RECIPE_ID, _ROLE_SUB_USAGE, _ROLE_SUB_MULT, _ROLE_SUB_TITLE):
            id_item.setData(role, None)
        id_item.setToolTip("")
        self._quick_input.clear()
        self._pending_catalog_id = None
        self._completion_model.setStringList([])
        self._catalog_pick_map.clear()
        self.data_changed.emit()

    def set_read_only(self, read_only: bool) -> None:
        super().set_read_only(read_only)
        self._quick_input.setReadOnly(read_only)
        self._quick_add_button.setEnabled(not read_only)
        self._pick_button.setEnabled(not read_only)
        self._sub_button.setEnabled(not read_only)
        self._save_pool_button.setEnabled(not read_only)

    def load_recipe(self, recipe: Recipe) -> None:
        self._current_recipe_id = recipe.id
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in sorted(recipe.ingredients, key=lambda row: row.display_order):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item.raw_text))
            self.table.setItem(row, 1, QTableWidgetItem("" if item.quantity_value is None else str(item.quantity_value)))
            self.table.setItem(row, 2, QTableWidgetItem(item.unit or ""))
            self.table.setItem(row, 3, QTableWidgetItem(item.ingredient_name or ""))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.is_optional).lower()))
            self.table.setItem(row, 5, QTableWidgetItem(item.preparation_notes or ""))
            id_item = self.table.item(row, 0)
            id_item.setData(Qt.ItemDataRole.UserRole, item.id)
            id_item.setData(_ROLE_CATALOG_ID, item.catalog_ingredient_id)
            id_item.setData(_ROLE_SUB_RECIPE_ID, item.sub_recipe_id)
            id_item.setData(_ROLE_SUB_USAGE, item.sub_recipe_usage_type)
            id_item.setData(_ROLE_SUB_MULT, item.sub_recipe_multiplier)
            id_item.setData(_ROLE_SUB_TITLE, item.sub_recipe_display_name)
            if item.sub_recipe_id:
                tip = (
                    f"Sub-recipe: {item.sub_recipe_display_name or '?'}\n"
                    f"Usage: {item.sub_recipe_usage_type or '?'}\n"
                    "Expands into that recipe’s ingredients for grocery generation."
                )
                id_item.setToolTip(tip)
            else:
                id_item.setToolTip("")
        self.table.blockSignals(False)

    def apply_to_recipe(self, recipe: Recipe) -> Recipe:
        items: list[RecipeIngredientItem] = []
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            item_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item and id_item.data(Qt.ItemDataRole.UserRole) else str(uuid4())
            catalog_id = id_item.data(_ROLE_CATALOG_ID) if id_item else None
            sub_id = id_item.data(_ROLE_SUB_RECIPE_ID) if id_item else None
            sub_usage = id_item.data(_ROLE_SUB_USAGE) if id_item else None
            sub_mult = id_item.data(_ROLE_SUB_MULT) if id_item else None
            sub_title = id_item.data(_ROLE_SUB_TITLE) if id_item else None
            raw_text = self.table.item(row, 0).text().strip() if self.table.item(row, 0) else ""
            quantity = self.table.item(row, 1).text().strip() if self.table.item(row, 1) else ""
            unit = self.table.item(row, 2).text().strip() if self.table.item(row, 2) else ""
            name = self.table.item(row, 3).text().strip() if self.table.item(row, 3) else ""
            optional = self.table.item(row, 4).text().strip().lower() if self.table.item(row, 4) else "false"
            prep_notes = self.table.item(row, 5).text().strip() if self.table.item(row, 5) else ""
            if not raw_text:
                continue
            qty_value = float(quantity) if quantity else None
            sub_recipe_id = str(sub_id) if sub_id else None
            if sub_recipe_id:
                catalog_id = None
            usage_typed = str(sub_usage) if sub_usage and sub_recipe_id else None
            mult_val: float | None = None
            if sub_recipe_id and usage_typed == "fraction_of_batch" and sub_mult is not None:
                mult_val = float(sub_mult)
            items.append(
                RecipeIngredientItem(
                    id=item_id,
                    raw_text=raw_text,
                    quantity_value=qty_value,
                    unit=unit or None,
                    ingredient_name=name or None,
                    is_optional=optional == "true",
                    display_order=row,
                    preparation_notes=prep_notes or None,
                    catalog_ingredient_id=str(catalog_id) if catalog_id else None,
                    sub_recipe_id=sub_recipe_id,
                    sub_recipe_usage_type=usage_typed if sub_recipe_id else None,
                    sub_recipe_multiplier=mult_val,
                    sub_recipe_display_name=(str(sub_title).strip() or None) if sub_recipe_id else None,
                )
            )
        recipe.ingredients = items
        return recipe

    def _pick_sub_recipe(self) -> None:
        dialog = SubRecipePickerDialog(self._editor, exclude_recipe_id=self._current_recipe_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        sel = dialog.selected()
        if not sel:
            QMessageBox.information(self, "No recipes", "Create another local recipe first, then link it here.")
            return
        usage = str(sel["usage"])
        title = str(sel["title"])
        mult = float(sel["multiplier"])
        if usage == "full_batch":
            line = f"Uses 1× {title}"
            mult_out = None
            usage_type = "full_batch"
        else:
            mult_display = str(mult).rstrip("0").rstrip(".") if "." in str(mult) else str(int(mult)) if mult == int(mult) else str(mult)
            line = f"Uses {mult_display}× {title}"
            mult_out = mult
            usage_type = "fraction_of_batch"
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(line))
        for column in range(1, 4):
            self.table.setItem(row, column, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem("false"))
        self.table.setItem(row, 5, QTableWidgetItem(""))
        id_item = self.table.item(row, 0)
        id_item.setData(Qt.ItemDataRole.UserRole, str(uuid4()))
        id_item.setData(_ROLE_CATALOG_ID, None)
        id_item.setData(_ROLE_SUB_RECIPE_ID, sel["sub_recipe_id"])
        id_item.setData(_ROLE_SUB_USAGE, usage_type)
        id_item.setData(_ROLE_SUB_MULT, mult_out)
        id_item.setData(_ROLE_SUB_TITLE, title)
        id_item.setToolTip(
            f"Sub-recipe: {title}\nUsage: {usage_type}\nExpands into that recipe’s ingredients for grocery generation."
        )
        self.data_changed.emit()
