"""Recipe library panel with search, filters, collections, and working set actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.app.services.editor_service import LibraryRecipeItem


class LibraryPanel(QWidget):
    recipe_selected = Signal(str, str)
    create_new_requested = Signal()
    duplicate_requested = Signal(str)
    search_changed = Signal(str, str, list)
    create_collection_requested = Signal()
    rename_collection_requested = Signal(str)
    delete_collection_requested = Signal(str)
    view_collection_requested = Signal(str)
    add_selected_to_collection_requested = Signal(str)
    add_selected_to_working_set_requested = Signal()
    remove_selected_from_working_set_requested = Signal()
    view_working_set_requested = Signal()
    view_favorites_requested = Signal()
    view_recent_opened_requested = Signal()
    view_recent_cooked_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search title, ingredients, tags, steps…")
        self.ingredient_focus_check = QCheckBox("Match ingredients only", self)
        self.ingredient_focus_check.setToolTip(
            "Only show recipes where the search text matches an ingredient line or linked catalog item name."
        )
        self.scope_filter = QComboBox(self)
        self.scope_filter.addItems(["all", "local", "bundled", "forked"])
        self.tag_filter_label = QLabel("Tags (recipes must include all checked)", self)
        self.tag_filter_list = QListWidget(self)
        self.tag_filter_list.setMaximumHeight(88)
        self.tag_filter_list.itemChanged.connect(lambda _: self._emit_search_change())
        self.list_widget = QListWidget(self)
        self.empty_state_label = QLabel(self)
        self.empty_state_label.setWordWrap(True)
        self.empty_state_label.hide()
        self.collections_list = QListWidget(self)

        self.new_button = QPushButton("New Local Recipe", self)
        self.duplicate_button = QPushButton("Duplicate Bundled to Local", self)
        self.add_to_working_set_button = QPushButton("Add To Working Set", self)
        self.remove_from_working_set_button = QPushButton("Remove From Working Set", self)
        self.view_working_set_button = QPushButton("View Working Set", self)
        self.view_favorites_button = QPushButton("Favorites", self)
        self.view_recent_opened_button = QPushButton("Recent Opened", self)
        self.view_recent_cooked_button = QPushButton("Recent Cooked", self)
        self.create_collection_button = QPushButton("New Collection", self)
        self.rename_collection_button = QPushButton("Rename Collection", self)
        self.delete_collection_button = QPushButton("Delete Collection", self)
        self.view_collection_button = QPushButton("View Collection", self)
        self.add_to_collection_button = QPushButton("Add Selected Recipe To Collection", self)

        self.new_button.clicked.connect(self.create_new_requested.emit)
        self.duplicate_button.clicked.connect(self._emit_duplicate)
        self.list_widget.itemSelectionChanged.connect(self._emit_selected)
        self.search_input.textChanged.connect(lambda _: self._emit_search_change())
        self.scope_filter.currentTextChanged.connect(lambda _: self._emit_search_change())
        self.ingredient_focus_check.stateChanged.connect(lambda _: self._emit_search_change())
        self.create_collection_button.clicked.connect(self.create_collection_requested.emit)
        self.rename_collection_button.clicked.connect(self._emit_rename_collection)
        self.delete_collection_button.clicked.connect(self._emit_delete_collection)
        self.view_collection_button.clicked.connect(self._emit_view_collection)
        self.add_to_collection_button.clicked.connect(self._emit_add_selected_to_collection)
        self.add_to_working_set_button.clicked.connect(self.add_selected_to_working_set_requested.emit)
        self.remove_from_working_set_button.clicked.connect(self.remove_selected_from_working_set_requested.emit)
        self.view_working_set_button.clicked.connect(self.view_working_set_requested.emit)
        self.view_favorites_button.clicked.connect(self.view_favorites_requested.emit)
        self.view_recent_opened_button.clicked.connect(self.view_recent_opened_requested.emit)
        self.view_recent_cooked_button.clicked.connect(self.view_recent_cooked_requested.emit)

        top_actions = QHBoxLayout()
        top_actions.addWidget(self.new_button)
        top_actions.addWidget(self.duplicate_button)

        ws_actions = QHBoxLayout()
        ws_actions.addWidget(self.add_to_working_set_button)
        ws_actions.addWidget(self.remove_from_working_set_button)
        ws_actions.addWidget(self.view_working_set_button)
        ws_actions2 = QHBoxLayout()
        ws_actions2.addWidget(self.view_favorites_button)
        ws_actions2.addWidget(self.view_recent_opened_button)
        ws_actions2.addWidget(self.view_recent_cooked_button)

        collection_actions1 = QHBoxLayout()
        collection_actions1.addWidget(self.create_collection_button)
        collection_actions1.addWidget(self.rename_collection_button)
        collection_actions1.addWidget(self.delete_collection_button)
        collection_actions2 = QHBoxLayout()
        collection_actions2.addWidget(self.view_collection_button)
        collection_actions2.addWidget(self.add_to_collection_button)

        root = QVBoxLayout(self)
        root.addWidget(self.search_input)
        root.addWidget(self.ingredient_focus_check)
        root.addWidget(self.scope_filter)
        root.addWidget(self.tag_filter_label)
        root.addWidget(self.tag_filter_list)
        root.addLayout(top_actions)
        root.addLayout(ws_actions)
        root.addLayout(ws_actions2)
        root.addWidget(self.empty_state_label)
        root.addWidget(self.list_widget)
        root.addWidget(QLabel("Collections"))
        root.addLayout(collection_actions1)
        root.addLayout(collection_actions2)
        root.addWidget(self.collections_list)
        self.setLayout(root)

        self._items: list[LibraryRecipeItem] = []

    def set_tag_filter_options(self, names: list[str]) -> None:
        self.tag_filter_list.blockSignals(True)
        self.tag_filter_list.clear()
        for name in sorted({n.strip() for n in names if n and str(n).strip()}, key=str.lower):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.tag_filter_list.addItem(item)
        self.tag_filter_list.blockSignals(False)

    def set_items(self, items: list[LibraryRecipeItem]) -> None:
        self._items = items
        self._refresh_list()

    def set_collections(self, collections: list[dict]) -> None:
        self.collections_list.clear()
        for collection in collections:
            self.collections_list.addItem(f"{collection['name']} ({collection['recipe_count']})")
            self.collections_list.item(self.collections_list.count() - 1).setData(256, collection["id"])

    def _rendered_item(self, item: LibraryRecipeItem) -> str:
        flags: list[str] = []
        if item.bundle_export_eligible:
            flags.append("EXPORT")
        if item.is_forked_from_bundled:
            flags.append("FORK")
        if item.is_favorite:
            flags.append("FAV")
        flag_text = f" [{'|'.join(flags)}]" if flags else ""
        hint = f" — {item.match_hints}" if item.match_hints else ""
        return f"[{item.source.upper()}] {item.title}{flag_text}{hint}"

    def _passes_scope_filter(self, item: LibraryRecipeItem) -> bool:
        scope = self.scope_filter.currentText()
        if scope == "local" and item.source != "local":
            return False
        if scope == "bundled" and item.source != "bundled":
            return False
        if scope == "forked" and not item.is_forked_from_bundled:
            return False
        return True

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        visible_count = 0
        for item in self._items:
            if not self._passes_scope_filter(item):
                continue
            self.list_widget.addItem(self._rendered_item(item))
            visible_count += 1
        if not self._items:
            self.empty_state_label.setText("No recipes yet. Click New Local Recipe to start, or import/sync when available.")
            self.empty_state_label.show()
        elif visible_count == 0:
            self.empty_state_label.setText("No matches for this search or scope. Try clearing the search box or changing scope.")
            self.empty_state_label.show()
        else:
            self.empty_state_label.hide()

    def _selected_item(self) -> LibraryRecipeItem | None:
        row = self.list_widget.currentRow()
        if row < 0:
            return None
        visible_items = [item for item in self._items if self._passes_scope_filter(item)]
        if row >= len(visible_items):
            return None
        return visible_items[row]

    def selected_tag_filters(self) -> list[str]:
        return self._selected_tag_filters()

    def ingredient_focus_enabled(self) -> bool:
        return self.ingredient_focus_check.isChecked()

    def _selected_collection_id(self) -> str | None:
        row = self.collections_list.currentRow()
        if row < 0:
            return None
        return self.collections_list.item(row).data(256)

    def _emit_selected(self) -> None:
        selected = self._selected_item()
        if selected is not None:
            self.recipe_selected.emit(selected.id, selected.source)

    def _emit_duplicate(self) -> None:
        selected = self._selected_item()
        if selected is not None and selected.source == "bundled":
            self.duplicate_requested.emit(selected.id)

    def _selected_tag_filters(self) -> list[str]:
        out: list[str] = []
        for i in range(self.tag_filter_list.count()):
            item = self.tag_filter_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(item.text())
        return out

    def _emit_search_change(self) -> None:
        self.search_changed.emit(
            self.search_input.text().strip(),
            self.scope_filter.currentText(),
            self._selected_tag_filters(),
        )
        self._refresh_list()

    def _emit_rename_collection(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id:
            self.rename_collection_requested.emit(collection_id)

    def _emit_delete_collection(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id:
            self.delete_collection_requested.emit(collection_id)

    def _emit_view_collection(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id:
            self.view_collection_requested.emit(collection_id)

    def _emit_add_selected_to_collection(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id:
            self.add_selected_to_collection_requested.emit(collection_id)

