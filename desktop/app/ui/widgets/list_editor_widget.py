"""Generic table-based list editor with reordering controls."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


class ListEditorWidget(QWidget):
    data_changed = Signal()

    def __init__(
        self,
        columns: list[str],
        parent: QWidget | None = None,
        *,
        extra_toolbar_widgets: Sequence[QWidget] | None = None,
    ):
        super().__init__(parent)
        self.table = QTableWidget(self)
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.itemChanged.connect(self.data_changed.emit)

        self.add_button = QPushButton("Add", self)
        self.delete_button = QPushButton("Delete", self)
        self.up_button = QPushButton("Move Up", self)
        self.down_button = QPushButton("Move Down", self)

        self.add_button.clicked.connect(self.add_empty_row)
        self.delete_button.clicked.connect(self.delete_selected_row)
        self.up_button.clicked.connect(self.move_selected_up)
        self.down_button.clicked.connect(self.move_selected_down)

        controls = QHBoxLayout()
        controls.addWidget(self.add_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.up_button)
        controls.addWidget(self.down_button)
        if extra_toolbar_widgets:
            for widget in extra_toolbar_widgets:
                controls.addWidget(widget)
        controls.addStretch()

        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.table)
        self.setLayout(root)

    def set_read_only(self, read_only: bool) -> None:
        self.table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
            if read_only
            else QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        self.add_button.setEnabled(not read_only)
        self.delete_button.setEnabled(not read_only)
        self.up_button.setEnabled(not read_only)
        self.down_button.setEnabled(not read_only)

    def add_empty_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.data_changed.emit()

    def delete_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.data_changed.emit()

    def move_selected_up(self) -> None:
        self._move_selected(-1)

    def move_selected_down(self) -> None:
        self._move_selected(1)

    def _move_selected(self, offset: int) -> None:
        row = self.table.currentRow()
        new_row = row + offset
        if row < 0 or new_row < 0 or new_row >= self.table.rowCount():
            return
        for column in range(self.table.columnCount()):
            current_item = self.table.takeItem(row, column)
            next_item = self.table.takeItem(new_row, column)
            self.table.setItem(row, column, next_item)
            self.table.setItem(new_row, column, current_item)
        self.table.setCurrentCell(new_row, 0)
        self.data_changed.emit()

