"""Equipment section editor."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

from desktop.app.domain.models import Recipe, RecipeEquipmentItem
from desktop.app.services.editor_service import EditorService
from desktop.app.ui.widgets.list_editor_widget import ListEditorWidget


class GlobalEquipmentPickerDialog(QDialog):
    def __init__(self, editor_service: EditorService, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("My Equipment")
        self._editor_service = editor_service
        self._selected: dict[str, str | None] | None = None

        self._filter = QLineEdit(self)
        self._filter.setPlaceholderText("Search…")
        self._list = QListWidget(self)

        self._new_name = QLineEdit(self)
        self._new_notes = QLineEdit(self)
        create_btn = QPushButton("Create & add to recipe", self)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Pick an item or create a new global entry.", self))
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

        self._rows: list[dict[str, str | None]] = []
        self._visible_rows: list[dict[str, str | None]] = []
        self._refresh_list()

    def selected(self) -> dict[str, str | None] | None:
        return self._selected

    def _refresh_list(self) -> None:
        needle = self._filter.text().strip().lower()
        self._rows = self._editor_service.list_global_equipment_summaries()
        self._list.clear()
        self._visible_rows = []
        for row in self._rows:
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
            QMessageBox.warning(self, "Name required", "Enter a name for the new equipment item.")
            return
        notes = self._new_notes.text().strip() or None
        try:
            ge_id = self._editor_service.create_global_equipment_record(name, notes=notes)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot create", str(exc))
            return
        self._selected = {"id": ge_id, "name": name, "notes": notes}
        self.accept()


class EquipmentPanel(ListEditorWidget):
    def __init__(self, editor_service: EditorService, parent: QWidget | None = None):
        self._editor = editor_service
        self._pick_button = QPushButton("My Equipment…", parent)
        self._pick_button.clicked.connect(self._pick_from_global)
        self._add_to_pool_button = QPushButton("Add & save to My Equipment", parent)
        self._add_to_pool_button.clicked.connect(self._add_row_and_pool)
        super().__init__(
            ["Name", "Description", "Required (true/false)", "Affiliate URL", "Alternate Equipment", "Notes"],
            parent,
            extra_toolbar_widgets=(self._pick_button, self._add_to_pool_button),
        )

    def load_recipe(self, recipe: Recipe) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in sorted(recipe.equipment, key=lambda row: row.display_order):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item.name))
            self.table.setItem(row, 1, QTableWidgetItem(item.description or ""))
            self.table.setItem(row, 2, QTableWidgetItem(str(item.is_required).lower()))
            self.table.setItem(row, 3, QTableWidgetItem(item.affiliate_url or ""))
            self.table.setItem(row, 4, QTableWidgetItem(item.alternate_equipment_text or ""))
            self.table.setItem(row, 5, QTableWidgetItem(item.notes or ""))
            id_item = self.table.item(row, 0)
            id_item.setData(Qt.ItemDataRole.UserRole, item.id)
            id_item.setData(Qt.ItemDataRole.UserRole + 1, item.global_equipment_id)
        self.table.blockSignals(False)

    def apply_to_recipe(self, recipe: Recipe) -> Recipe:
        items: list[RecipeEquipmentItem] = []
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            item_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item and id_item.data(Qt.ItemDataRole.UserRole) else str(uuid4())
            global_id = id_item.data(Qt.ItemDataRole.UserRole + 1) if id_item else None
            name = self.table.item(row, 0).text().strip() if self.table.item(row, 0) else ""
            description = self.table.item(row, 1).text().strip() if self.table.item(row, 1) else ""
            required_text = self.table.item(row, 2).text().strip().lower() if self.table.item(row, 2) else "true"
            affiliate = self.table.item(row, 3).text().strip() if self.table.item(row, 3) else ""
            alternate = self.table.item(row, 4).text().strip() if self.table.item(row, 4) else ""
            notes = self.table.item(row, 5).text().strip() if self.table.item(row, 5) else ""
            if not name:
                continue
            items.append(
                RecipeEquipmentItem(
                    id=item_id,
                    name=name,
                    is_required=required_text != "false",
                    display_order=row,
                    description=description or None,
                    affiliate_url=affiliate or None,
                    alternate_equipment_text=alternate or None,
                    notes=notes or None,
                    global_equipment_id=str(global_id) if global_id else None,
                )
            )
        recipe.equipment = items
        return recipe

    def _pick_from_global(self) -> None:
        dialog = GlobalEquipmentPickerDialog(self._editor, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        sel = dialog.selected()
        if not sel:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(sel["name"] or ""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem("true"))
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem(""))
        notes = sel.get("notes") or ""
        self.table.setItem(row, 5, QTableWidgetItem(str(notes)))
        id_item = self.table.item(row, 0)
        id_item.setData(Qt.ItemDataRole.UserRole, str(uuid4()))
        id_item.setData(Qt.ItemDataRole.UserRole + 1, sel["id"])
        self.data_changed.emit()

    def _add_row_and_pool(self) -> None:
        name, ok = QInputDialog.getText(self, "Save to My Equipment", "Equipment name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        try:
            ge_id = self._editor.create_global_equipment_record(name)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot create", str(exc))
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem("true"))
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem(""))
        self.table.setItem(row, 5, QTableWidgetItem(""))
        id_item = self.table.item(row, 0)
        id_item.setData(Qt.ItemDataRole.UserRole, str(uuid4()))
        id_item.setData(Qt.ItemDataRole.UserRole + 1, ge_id)
        self.data_changed.emit()
