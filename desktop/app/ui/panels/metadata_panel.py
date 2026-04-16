"""Recipe metadata editor panel."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from desktop.app.domain.models import Recipe


class MetadataPanel(QWidget):
    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.title_input = QLineEdit(self)
        self.subtitle_input = QLineEdit(self)
        self.author_input = QLineEdit(self)
        self.source_name_input = QLineEdit(self)
        self.source_url_input = QLineEdit(self)
        self.difficulty_input = QLineEdit(self)
        self.servings_input = QLineEdit(self)
        self.status_input = QLineEdit(self)
        self.bundle_export_eligible_input = QCheckBox(self)
        self.prep_minutes = QSpinBox(self)
        self.cook_minutes = QSpinBox(self)
        self.total_minutes = QSpinBox(self)
        for spin in (self.prep_minutes, self.cook_minutes, self.total_minutes):
            spin.setRange(0, 50000)
        self.notes_input = QPlainTextEdit(self)

        tags_box = QGroupBox("Tags", self)
        tags_layout = QVBoxLayout()
        self._tags_list = QListWidget(self)
        self._tags_list.setMaximumHeight(100)
        tag_row = QHBoxLayout()
        self._tag_combo = QComboBox(self)
        self._tag_combo.setEditable(True)
        self._add_tag_button = QPushButton("Add tag", self)
        self._remove_tag_button = QPushButton("Remove selected", self)
        tag_row.addWidget(self._tag_combo, stretch=1)
        tag_row.addWidget(self._add_tag_button)
        tag_row.addWidget(self._remove_tag_button)
        tags_layout.addWidget(self._tags_list)
        tags_layout.addLayout(tag_row)
        tags_box.setLayout(tags_layout)

        start_label = QLabel("Start here", self)
        start_label.setStyleSheet("font-weight: 600")
        self.title_input.setPlaceholderText("Recipe name (required)")

        essential = QFormLayout()
        essential.addRow("Recipe name", self.title_input)
        essential.addRow("Notes", self.notes_input)

        optional_box = QGroupBox("More details (optional)", self)
        optional_form = QFormLayout()
        optional_form.addRow("Subtitle", self.subtitle_input)
        optional_form.addRow("Author", self.author_input)
        optional_form.addRow("Source Name", self.source_name_input)
        optional_form.addRow("Source URL", self.source_url_input)
        optional_form.addRow("Difficulty", self.difficulty_input)
        optional_form.addRow("Servings", self.servings_input)
        optional_form.addRow("Status", self.status_input)
        optional_form.addRow("Bundled Export Eligible", self.bundle_export_eligible_input)

        times = QHBoxLayout()
        times.addWidget(self.prep_minutes)
        times.addWidget(self.cook_minutes)
        times.addWidget(self.total_minutes)
        optional_form.addRow("Prep/Cook/Total (min)", times)
        self.provenance_label = QLabel(self)
        optional_form.addRow("Provenance", self.provenance_label)
        optional_box.setLayout(optional_form)

        root = QVBoxLayout(self)
        root.addWidget(start_label)
        root.addLayout(essential)
        root.addWidget(tags_box)
        root.addWidget(optional_box)
        self.setLayout(root)

        for widget in (
            self.title_input,
            self.subtitle_input,
            self.author_input,
            self.source_name_input,
            self.source_url_input,
            self.difficulty_input,
            self.servings_input,
            self.status_input,
        ):
            widget.textChanged.connect(self.data_changed.emit)
        for spin in (self.prep_minutes, self.cook_minutes, self.total_minutes):
            spin.valueChanged.connect(self.data_changed.emit)
        self.notes_input.textChanged.connect(self.data_changed.emit)
        self.bundle_export_eligible_input.stateChanged.connect(self.data_changed.emit)
        self._add_tag_button.clicked.connect(self._on_add_tag)
        self._remove_tag_button.clicked.connect(self._on_remove_tag)

    def set_available_tags(self, names: list[str]) -> None:
        text = self._tag_combo.currentText()
        self._tag_combo.blockSignals(True)
        self._tag_combo.clear()
        for name in sorted({n.strip() for n in names if n and str(n).strip()}, key=str.lower):
            self._tag_combo.addItem(name)
        self._tag_combo.setEditText(text)
        self._tag_combo.blockSignals(False)

    def _on_add_tag(self) -> None:
        raw = self._tag_combo.currentText().strip()
        if not raw:
            return
        existing = {self._tags_list.item(i).text().lower() for i in range(self._tags_list.count())}
        if raw.lower() in existing:
            return
        self._tags_list.addItem(raw)
        self.data_changed.emit()

    def _on_remove_tag(self) -> None:
        row = self._tags_list.currentRow()
        if row >= 0:
            self._tags_list.takeItem(row)
            self.data_changed.emit()

    def set_read_only(self, read_only: bool) -> None:
        for widget in (
            self.title_input,
            self.subtitle_input,
            self.author_input,
            self.source_name_input,
            self.source_url_input,
            self.difficulty_input,
            self.servings_input,
            self.status_input,
            self.notes_input,
        ):
            widget.setReadOnly(read_only)
        self.bundle_export_eligible_input.setEnabled(not read_only)
        for spin in (self.prep_minutes, self.cook_minutes, self.total_minutes):
            spin.setEnabled(not read_only)
        self._tags_list.setEnabled(not read_only)
        self._tag_combo.setEnabled(not read_only)
        self._add_tag_button.setEnabled(not read_only)
        self._remove_tag_button.setEnabled(not read_only)

    def load_recipe(self, recipe: Recipe) -> None:
        self.title_input.setText(recipe.title)
        self.subtitle_input.setText(recipe.subtitle or "")
        self.author_input.setText(recipe.author or "")
        self.source_name_input.setText(recipe.source_name or "")
        self.source_url_input.setText(recipe.source_url or "")
        self.difficulty_input.setText(recipe.difficulty or "")
        self.servings_input.setText("" if recipe.servings is None else str(recipe.servings))
        self.status_input.setText(recipe.status)
        self.prep_minutes.setValue(recipe.prep_minutes or 0)
        self.cook_minutes.setValue(recipe.cook_minutes or 0)
        self.total_minutes.setValue(recipe.total_minutes or 0)
        self.notes_input.setPlainText(recipe.notes or "")
        self.bundle_export_eligible_input.setChecked(recipe.bundle_export_eligible)
        self._tags_list.clear()
        for tag in recipe.tags or []:
            if tag and str(tag).strip():
                self._tags_list.addItem(str(tag).strip())
        if recipe.is_forked_from_bundled and recipe.origin_bundled_recipe_id:
            self.provenance_label.setText(
                f"Local fork of bundled {recipe.origin_bundled_recipe_id} (v{recipe.origin_bundled_recipe_version or '-'})"
            )
        elif recipe.export_bundle_recipe_id:
            self.provenance_label.setText(
                f"Bundled export id {recipe.export_bundle_recipe_id} (v{recipe.export_bundle_recipe_version})"
            )
        else:
            self.provenance_label.setText("Local recipe")

    def apply_to_recipe(self, recipe: Recipe) -> Recipe:
        recipe.title = self.title_input.text().strip() or "Untitled Recipe"
        recipe.subtitle = self.subtitle_input.text().strip() or None
        recipe.author = self.author_input.text().strip() or None
        recipe.source_name = self.source_name_input.text().strip() or None
        recipe.source_url = self.source_url_input.text().strip() or None
        recipe.difficulty = self.difficulty_input.text().strip() or None
        servings_text = self.servings_input.text().strip()
        recipe.servings = float(servings_text) if servings_text else None
        recipe.status = self.status_input.text().strip() or "draft"
        recipe.prep_minutes = self.prep_minutes.value()
        recipe.cook_minutes = self.cook_minutes.value()
        recipe.total_minutes = self.total_minutes.value()
        recipe.notes = self.notes_input.toPlainText().strip() or None
        recipe.bundle_export_eligible = self.bundle_export_eligible_input.isChecked()
        tags: list[str] = []
        seen: set[str] = set()
        for i in range(self._tags_list.count()):
            t = self._tags_list.item(i).text().strip()
            if not t:
                continue
            k = t.lower()
            if k in seen:
                continue
            seen.add(k)
            tags.append(t)
        recipe.tags = tags
        return recipe

