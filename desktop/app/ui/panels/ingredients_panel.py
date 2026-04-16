"""Ingredients section editor supporting raw and structured entry."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QTableWidgetItem, QWidget

from desktop.app.domain.models import Recipe, RecipeIngredientItem
from desktop.app.ui.widgets.list_editor_widget import ListEditorWidget


class IngredientsPanel(ListEditorWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(
            ["Ingredient line", "Quantity", "Unit", "Name", "Optional (true/false)", "Preparation Notes"],
            parent,
        )
        self._quick_input = QLineEdit(self)
        self._quick_input.setPlaceholderText("Type a line, e.g. 2 cups flour — then Add line")
        self._quick_add_button = QPushButton("Add line", self)
        self._quick_add_button.clicked.connect(self._quick_add_row)
        self._quick_input.returnPressed.connect(self._quick_add_row)
        quick_row = QHBoxLayout()
        quick_row.addWidget(self._quick_input, stretch=1)
        quick_row.addWidget(self._quick_add_button)
        root_layout = self.layout()
        assert root_layout is not None
        root_layout.insertLayout(1, quick_row)

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
        self._quick_input.clear()
        self.data_changed.emit()

    def set_read_only(self, read_only: bool) -> None:
        super().set_read_only(read_only)
        self._quick_input.setReadOnly(read_only)
        self._quick_add_button.setEnabled(not read_only)

    def load_recipe(self, recipe: Recipe) -> None:
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
            self.table.item(row, 0).setData(256, item.id)
        self.table.blockSignals(False)

    def apply_to_recipe(self, recipe: Recipe) -> Recipe:
        from uuid import uuid4

        items: list[RecipeIngredientItem] = []
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            item_id = id_item.data(256) if id_item and id_item.data(256) else str(uuid4())
            raw_text = self.table.item(row, 0).text().strip() if self.table.item(row, 0) else ""
            quantity = self.table.item(row, 1).text().strip() if self.table.item(row, 1) else ""
            unit = self.table.item(row, 2).text().strip() if self.table.item(row, 2) else ""
            name = self.table.item(row, 3).text().strip() if self.table.item(row, 3) else ""
            optional = self.table.item(row, 4).text().strip().lower() if self.table.item(row, 4) else "false"
            prep_notes = self.table.item(row, 5).text().strip() if self.table.item(row, 5) else ""
            if not raw_text:
                continue
            qty_value = float(quantity) if quantity else None
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
                )
            )
        recipe.ingredients = items
        return recipe

