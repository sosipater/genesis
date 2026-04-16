"""Steps editor with structured link/timer authoring and preview."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from desktop.app.domain.models import Recipe, RecipeStep
from desktop.app.services.editor_service import EditorService
from desktop.app.services.step_authoring_service import StepAuthoringService
from desktop.app.ui.timer_alert_mapping import SOUND_PRESET_CHOICES, label_for_sound_key, sound_key_for_label


_REF_SLUG = re.compile(r"[^a-z0-9]+")


def _reference_name_from_target_label(text: str) -> str:
    base = _REF_SLUG.sub("_", text.strip().lower()).strip("_")
    return base or "item"


class StepsPanel(QWidget):
    data_changed = Signal()

    def __init__(self, editor_service: EditorService | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._editor_service = editor_service
        self._service = StepAuthoringService()
        self._recipe: Recipe | None = None
        self._read_only = False
        self._updating = False

        self.step_list = QListWidget(self)
        self.add_step_button = QPushButton("Add Step", self)
        self.remove_step_button = QPushButton("Remove Step", self)
        self.move_up_button = QPushButton("Move Up", self)
        self.move_down_button = QPushButton("Move Down", self)

        self.step_title_input = QLineEdit(self)
        self.step_type_input = QComboBox(self)
        self.step_type_input.addItems(["instruction", "note", "section_break"])
        self.estimated_seconds_input = QSpinBox(self)
        self.estimated_seconds_input.setRange(0, 86_400)
        self.step_body_input = QPlainTextEdit(self)

        self.links_table = QTableWidget(self)
        self.links_table.setColumnCount(4)
        self.links_table.setHorizontalHeaderLabels(
            ["Target Type", "Target", "Reference name", "Display text (optional)"]
        )
        self.add_link_button = QPushButton("Add Link", self)
        self.edit_link_button = QPushButton("Edit Link", self)
        self.remove_link_button = QPushButton("Remove Link", self)

        self.timers_table = QTableWidget(self)
        self.timers_table.setColumnCount(5)
        self.timers_table.setHorizontalHeaderLabels(
            ["Label", "Duration (s)", "Auto Start", "Sound", "Vibrate"]
        )
        self.add_timer_button = QPushButton("Add Timer", self)
        self.edit_timer_button = QPushButton("Edit Timer", self)
        self.remove_timer_button = QPushButton("Remove Timer", self)

        self.preview_browser = QTextBrowser(self)

        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_controls = QHBoxLayout()
        left_controls.addWidget(self.add_step_button)
        left_controls.addWidget(self.remove_step_button)
        left_controls.addWidget(self.move_up_button)
        left_controls.addWidget(self.move_down_button)
        left_layout.addLayout(left_controls)
        left_layout.addWidget(self.step_list)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        form = QFormLayout()
        form.addRow("Title", self.step_title_input)
        form.addRow("Step Type", self.step_type_input)
        form.addRow("Estimated Seconds", self.estimated_seconds_input)
        form.addRow("Body", self.step_body_input)
        right_layout.addLayout(form)

        self.advanced_group = QGroupBox("Advanced (optional)", self)
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        optional_layout = QVBoxLayout(self.advanced_group)

        self._step_image_label = QLabel("No step image", self)
        img_row = QHBoxLayout()
        self._attach_step_image_btn = QPushButton("Attach image…", self)
        self._remove_step_image_btn = QPushButton("Remove image", self)
        img_row.addWidget(self._step_image_label, stretch=1)
        img_row.addWidget(self._attach_step_image_btn)
        img_row.addWidget(self._remove_step_image_btn)
        optional_layout.addLayout(img_row)

        optional_layout.addWidget(QLabel("Step links"))
        link_controls = QHBoxLayout()
        link_controls.addWidget(self.add_link_button)
        link_controls.addWidget(self.edit_link_button)
        link_controls.addWidget(self.remove_link_button)
        optional_layout.addLayout(link_controls)
        optional_layout.addWidget(self.links_table)

        optional_layout.addWidget(QLabel("Step timers"))
        timer_controls = QHBoxLayout()
        timer_controls.addWidget(self.add_timer_button)
        timer_controls.addWidget(self.edit_timer_button)
        timer_controls.addWidget(self.remove_timer_button)
        optional_layout.addLayout(timer_controls)
        optional_layout.addWidget(self.timers_table)
        right_layout.addWidget(self.advanced_group)

        right_layout.addWidget(QLabel("Interaction preview"))
        right_layout.addWidget(self.preview_browser)

        splitter = QSplitter(self)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([280, 820])
        root = QVBoxLayout(self)
        root.addWidget(splitter)
        self.setLayout(root)

    def _wire_signals(self) -> None:
        self.step_list.currentRowChanged.connect(self._on_step_selected)
        self.add_step_button.clicked.connect(self._add_step)
        self.remove_step_button.clicked.connect(self._remove_step)
        self.move_up_button.clicked.connect(lambda: self._move_step(-1))
        self.move_down_button.clicked.connect(lambda: self._move_step(1))

        self.step_title_input.textChanged.connect(self._on_step_fields_changed)
        self.step_type_input.currentTextChanged.connect(self._on_step_fields_changed)
        self.estimated_seconds_input.valueChanged.connect(self._on_step_fields_changed)
        self.step_body_input.textChanged.connect(self._on_step_fields_changed)

        self.add_link_button.clicked.connect(self._add_link)
        self.edit_link_button.clicked.connect(self._edit_link)
        self.remove_link_button.clicked.connect(self._remove_link)

        self.add_timer_button.clicked.connect(self._add_timer)
        self.edit_timer_button.clicked.connect(self._edit_timer)
        self.remove_timer_button.clicked.connect(self._remove_timer)

        self._attach_step_image_btn.clicked.connect(self._on_attach_step_image)
        self._remove_step_image_btn.clicked.connect(self._on_remove_step_image)

        self.preview_browser.anchorClicked.connect(self._on_preview_anchor_clicked)

    def load_recipe(self, recipe: Recipe) -> None:
        self._recipe = recipe
        self._updating = True
        self.step_list.clear()
        for step in sorted(recipe.steps, key=lambda item: item.display_order):
            item = QListWidgetItem(step.title or f"Step {step.display_order + 1}")
            item.setData(256, step.id)
            self.step_list.addItem(item)
        if self.step_list.count() > 0:
            self.step_list.setCurrentRow(0)
        else:
            self._clear_editor()
        self._updating = False
        self._refresh_preview()

    def apply_to_recipe(self, recipe: Recipe) -> Recipe:
        if self._recipe is not None and self._recipe.id == recipe.id:
            recipe.steps = self._recipe.steps
            recipe.step_links = self._recipe.step_links
        return recipe

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = read_only
        for widget in (
            self.add_step_button,
            self.remove_step_button,
            self.move_up_button,
            self.move_down_button,
            self.step_title_input,
            self.step_type_input,
            self.estimated_seconds_input,
            self.step_body_input,
            self.add_link_button,
            self.edit_link_button,
            self.remove_link_button,
            self.add_timer_button,
            self.edit_timer_button,
            self.remove_timer_button,
            self._attach_step_image_btn,
            self._remove_step_image_btn,
            self.advanced_group,
        ):
            widget.setEnabled(not read_only)

    def _current_step(self) -> RecipeStep | None:
        if self._recipe is None:
            return None
        row = self.step_list.currentRow()
        if row < 0 or row >= len(self._recipe.steps):
            return None
        ordered_steps = sorted(self._recipe.steps, key=lambda st: st.display_order)
        return ordered_steps[row]

    def _on_step_selected(self, _: int) -> None:
        self._load_selected_step()

    def _load_selected_step(self) -> None:
        step = self._current_step()
        self._updating = True
        if step is None:
            self._clear_editor()
            self._updating = False
            return
        self.step_title_input.setText(step.title or "")
        self.step_type_input.setCurrentText(step.step_type)
        self.estimated_seconds_input.setValue(step.estimated_seconds or 0)
        self.step_body_input.setPlainText(step.body_text)
        self._refresh_step_image_label(step)
        self._load_links(step.id)
        self._load_timers(step)
        self._updating = False
        self._refresh_preview()

    def _clear_editor(self) -> None:
        self.step_title_input.clear()
        self.step_type_input.setCurrentIndex(0)
        self.estimated_seconds_input.setValue(0)
        self.step_body_input.clear()
        self.links_table.setRowCount(0)
        self.timers_table.setRowCount(0)
        self._step_image_label.setText("No step image")
        self.preview_browser.clear()

    def _refresh_step_image_label(self, step: RecipeStep) -> None:
        if step.media_id:
            short = step.media_id[:8] + "…" if len(step.media_id) > 10 else step.media_id
            self._step_image_label.setText(f"Image: {short}")
        else:
            self._step_image_label.setText("No step image")

    def _on_attach_step_image(self) -> None:
        step = self._current_step()
        if self._recipe is None or step is None or self._editor_service is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Attach step image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp);;All files (*)",
        )
        if not path:
            return
        try:
            self._editor_service.attach_step_media(self._recipe, step.id, Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "Attach failed", str(exc))
            return
        self._refresh_step_image_label(step)
        self.data_changed.emit()

    def _on_remove_step_image(self) -> None:
        step = self._current_step()
        if self._recipe is None or step is None or self._editor_service is None:
            return
        try:
            self._editor_service.remove_step_media(self._recipe, step.id)
        except Exception as exc:
            QMessageBox.warning(self, "Remove failed", str(exc))
            return
        self._refresh_step_image_label(step)
        self.data_changed.emit()

    def _on_step_fields_changed(self) -> None:
        if self._updating or self._recipe is None:
            return
        step = self._current_step()
        if step is None:
            return
        step.title = self.step_title_input.text().strip() or None
        step.step_type = self.step_type_input.currentText()  # type: ignore[assignment]
        step.estimated_seconds = self.estimated_seconds_input.value() or None
        step.body_text = self.step_body_input.toPlainText().strip()
        row = self.step_list.currentRow()
        if row >= 0:
            self.step_list.item(row).setText(step.title or f"Step {row + 1}")
        self._refresh_preview()
        self.data_changed.emit()

    def _add_step(self) -> None:
        if self._recipe is None:
            return
        new_step = RecipeStep(
            id=str(uuid4()),
            title=f"Step {len(self._recipe.steps) + 1}",
            body_text="Add instruction here.",
            step_type="instruction",
            estimated_seconds=None,
            display_order=len(self._recipe.steps),
            timers=[],
        )
        self._recipe.steps.append(new_step)
        self.load_recipe(self._recipe)
        self.step_list.setCurrentRow(len(self._recipe.steps) - 1)
        self.advanced_group.setChecked(True)
        self.data_changed.emit()

    def _remove_step(self) -> None:
        if self._recipe is None:
            return
        step = self._current_step()
        if step is None:
            return
        self._recipe.steps = [item for item in self._recipe.steps if item.id != step.id]
        self._recipe.step_links = [lnk for lnk in self._recipe.step_links if lnk.step_id != step.id]
        self._renumber_steps()
        self.load_recipe(self._recipe)
        self.data_changed.emit()

    def _move_step(self, offset: int) -> None:
        if self._recipe is None:
            return
        ordered = sorted(self._recipe.steps, key=lambda st: st.display_order)
        row = self.step_list.currentRow()
        new_row = row + offset
        if row < 0 or new_row < 0 or new_row >= len(ordered):
            return
        ordered[row], ordered[new_row] = ordered[new_row], ordered[row]
        for idx, step in enumerate(ordered):
            step.display_order = idx
        self._recipe.steps = ordered
        self.load_recipe(self._recipe)
        self.step_list.setCurrentRow(new_row)
        self.data_changed.emit()

    def _renumber_steps(self) -> None:
        if self._recipe is None:
            return
        for idx, step in enumerate(sorted(self._recipe.steps, key=lambda st: st.display_order)):
            step.display_order = idx

    def _load_links(self, step_id: str) -> None:
        if self._recipe is None:
            return
        links = [lnk for lnk in self._recipe.step_links if lnk.step_id == step_id]
        self.links_table.setRowCount(0)
        for link in links:
            row = self.links_table.rowCount()
            self.links_table.insertRow(row)
            self.links_table.setItem(row, 0, QTableWidgetItem(link.target_type))
            self.links_table.setItem(row, 1, QTableWidgetItem(self._target_display(link.target_type, link.target_id)))
            self.links_table.setItem(row, 2, QTableWidgetItem(link.token_key))
            self.links_table.setItem(row, 3, QTableWidgetItem(link.label_override or ""))
            self.links_table.item(row, 0).setData(256, link.id)

    def _target_display(self, target_type: str, target_id: str) -> str:
        if self._recipe is None:
            return target_id
        if target_type == "ingredient":
            item = next((ing for ing in self._recipe.ingredients if ing.id == target_id), None)
            return item.raw_text if item else target_id
        item = next((eq for eq in self._recipe.equipment if eq.id == target_id), None)
        return item.name if item else target_id

    def _add_link(self) -> None:
        if self._recipe is None:
            return
        step = self._current_step()
        if step is None:
            return
        dialog = LinkEditorDialog(self._recipe, parent=self)
        if not dialog.exec():
            return
        try:
            self._service.add_link(
                self._recipe,
                step.id,
                dialog.target_type,
                dialog.target_id,
                dialog.token_key,
                dialog.label_snapshot,
                dialog.label_override,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Link", str(exc))
            return
        self._load_selected_step()
        self.data_changed.emit()

    def _edit_link(self) -> None:
        if self._recipe is None:
            return
        row = self.links_table.currentRow()
        if row < 0:
            return
        link_id_item = self.links_table.item(row, 0)
        if link_id_item is None:
            return
        link_id = link_id_item.data(256)
        link = next((lnk for lnk in self._recipe.step_links if lnk.id == link_id), None)
        if link is None:
            return
        dialog = LinkEditorDialog(self._recipe, existing=link, parent=self)
        if not dialog.exec():
            return
        try:
            self._service.update_link(
                self._recipe,
                link.id,
                token_key=dialog.token_key,
                label_override=dialog.label_override,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Link", str(exc))
            return
        self._load_selected_step()
        self.data_changed.emit()

    def _remove_link(self) -> None:
        if self._recipe is None:
            return
        row = self.links_table.currentRow()
        if row < 0:
            return
        link_id_item = self.links_table.item(row, 0)
        if link_id_item is None:
            return
        link_id = link_id_item.data(256)
        self._service.remove_link(self._recipe, link_id)
        self._load_selected_step()
        self.data_changed.emit()

    def _load_timers(self, step: RecipeStep) -> None:
        self.timers_table.setRowCount(0)
        for timer in step.timers:
            row = self.timers_table.rowCount()
            self.timers_table.insertRow(row)
            self.timers_table.setItem(row, 0, QTableWidgetItem(timer.label))
            self.timers_table.setItem(row, 1, QTableWidgetItem(str(timer.duration_seconds)))
            self.timers_table.setItem(row, 2, QTableWidgetItem("yes" if timer.auto_start else "no"))
            self.timers_table.setItem(row, 3, QTableWidgetItem(label_for_sound_key(timer.alert_sound_key)))
            self.timers_table.setItem(row, 4, QTableWidgetItem("yes" if timer.alert_vibrate else "no"))
            self.timers_table.item(row, 0).setData(256, timer.id)

    def _add_timer(self) -> None:
        step = self._current_step()
        if step is None:
            return
        dialog = TimerEditorDialog(parent=self)
        if not dialog.exec():
            return
        try:
            self._service.add_timer(
                step,
                dialog.label,
                dialog.duration_seconds,
                dialog.auto_start,
                dialog.alert_sound_key,
                alert_vibrate=dialog.alert_vibrate,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Timer", str(exc))
            return
        self._load_selected_step()
        self.data_changed.emit()

    def _edit_timer(self) -> None:
        step = self._current_step()
        if step is None:
            return
        row = self.timers_table.currentRow()
        if row < 0:
            return
        timer_id_item = self.timers_table.item(row, 0)
        if timer_id_item is None:
            return
        timer_id = timer_id_item.data(256)
        timer = next((t for t in step.timers if t.id == timer_id), None)
        if timer is None:
            return
        dialog = TimerEditorDialog(existing=timer, parent=self)
        if not dialog.exec():
            return
        try:
            self._service.update_timer(
                step,
                timer.id,
                label=dialog.label,
                duration_seconds=dialog.duration_seconds,
                auto_start=dialog.auto_start,
                alert_sound_key=dialog.alert_sound_key,
                alert_vibrate=dialog.alert_vibrate,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Timer", str(exc))
            return
        self._load_selected_step()
        self.data_changed.emit()

    def _remove_timer(self) -> None:
        step = self._current_step()
        if step is None:
            return
        row = self.timers_table.currentRow()
        if row < 0:
            return
        timer_id_item = self.timers_table.item(row, 0)
        if timer_id_item is None:
            return
        timer_id = timer_id_item.data(256)
        self._service.remove_timer(step, timer_id)
        self._load_selected_step()
        self.data_changed.emit()

    def _refresh_preview(self) -> None:
        if self._recipe is None:
            self.preview_browser.setHtml("")
            return
        step = self._current_step()
        if step is None:
            self.preview_browser.setHtml("")
            return
        segments = self._service.render_preview_segments(self._recipe, step)
        html_parts: list[str] = []
        for text, link in segments:
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if link is None:
                html_parts.append(safe)
            else:
                html_parts.append(f'<a href="{link.id}"><span style="color:#66b3ff">{safe}</span></a>')
        self.preview_browser.setHtml("".join(html_parts))

    def _on_preview_anchor_clicked(self, url) -> None:  # type: ignore[no-untyped-def]
        if self._recipe is None:
            return
        link_id = url.toString()
        link = next((lnk for lnk in self._recipe.step_links if lnk.id == link_id), None)
        if link is None:
            return
        if link.target_type == "ingredient":
            ingredient = next((ing for ing in self._recipe.ingredients if ing.id == link.target_id), None)
            if ingredient is None:
                QMessageBox.information(self, "Missing Link Target", f"Ingredient missing for {link.label_snapshot}")
                return
            QMessageBox.information(
                self,
                "Ingredient Detail",
                f"{ingredient.raw_text}\n"
                f"Name: {ingredient.ingredient_name or '-'}\n"
                f"Substitutions: {ingredient.substitutions or '-'}\n"
                f"Notes: {ingredient.preparation_notes or '-'}",
            )
            return
        equipment = next((eq for eq in self._recipe.equipment if eq.id == link.target_id), None)
        if equipment is None:
            QMessageBox.information(self, "Missing Link Target", f"Equipment missing for {link.label_snapshot}")
            return
        QMessageBox.information(
            self,
            "Equipment Detail",
            f"{equipment.name}\n"
            f"Description: {equipment.description or '-'}\n"
            f"Required: {'yes' if equipment.is_required else 'no'}\n"
            f"Notes: {equipment.notes or '-'}\n"
            f"Affiliate: {equipment.affiliate_url or '-'}",
        )


class LinkEditorDialog(QDialog):
    def __init__(self, recipe: Recipe, existing=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit step link" if existing else "Add step link")
        self.target_type_input = QComboBox(self)
        self.target_type_input.addItems(["ingredient", "equipment"])
        self.target_input = QComboBox(self)
        self.reference_name_input = QLineEdit(self)
        self.display_text_input = QLineEdit(self)
        self._reference_user_edited = existing is not None
        self._last_auto_reference = ""

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Target type", self.target_type_input)
        form.addRow("Target item", self.target_input)
        help_lbl = QLabel(
            "Reference name is used internally to connect this step to the selected item. "
            "You normally do not need to change it.",
            self,
        )
        help_lbl.setWordWrap(True)
        layout.addWidget(help_lbl)
        form.addRow("Reference name", self.reference_name_input)
        form.addRow("Display text (optional)", self.display_text_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.reference_name_input.textEdited.connect(lambda _: setattr(self, "_reference_user_edited", True))

        self.target_type_input.currentTextChanged.connect(lambda _: self._populate_targets(recipe, refresh_reference=True))
        self.target_input.currentIndexChanged.connect(lambda _: self._maybe_autofill_reference())
        self._populate_targets(recipe, refresh_reference=False)
        if existing is not None:
            self.target_type_input.setCurrentText(existing.target_type)
            self._populate_targets(recipe, refresh_reference=False)
            self.target_input.setCurrentText(self._target_text(recipe, existing.target_type, existing.target_id))
            self.reference_name_input.setText(existing.token_key)
            self.display_text_input.setText(existing.label_override or "")
            self._last_auto_reference = _reference_name_from_target_label(self.target_input.currentText())

    @property
    def target_type(self) -> str:
        return self.target_type_input.currentText()

    @property
    def target_id(self) -> str:
        idx = self.target_input.currentIndex()
        return self.target_input.itemData(idx)

    @property
    def token_key(self) -> str:
        return self.reference_name_input.text().strip()

    @property
    def label_snapshot(self) -> str:
        return self.target_input.currentText().strip()

    @property
    def label_override(self) -> str | None:
        value = self.display_text_input.text().strip()
        return value or None

    def _maybe_autofill_reference(self) -> None:
        if self._reference_user_edited:
            return
        label = self.target_input.currentText().strip()
        auto = _reference_name_from_target_label(label)
        prev_auto = self._last_auto_reference
        current = self.reference_name_input.text().strip()
        if not current or current == prev_auto:
            self.reference_name_input.setText(auto)
        self._last_auto_reference = auto

    def _populate_targets(self, recipe: Recipe, *, refresh_reference: bool) -> None:
        self.target_input.clear()
        if self.target_type_input.currentText() == "ingredient":
            for item in recipe.ingredients:
                self.target_input.addItem(item.raw_text, userData=item.id)
        else:
            for item in recipe.equipment:
                self.target_input.addItem(item.name, userData=item.id)
        if refresh_reference:
            self._reference_user_edited = False
        self._maybe_autofill_reference()

    def _target_text(self, recipe: Recipe, target_type: str, target_id: str) -> str:
        if target_type == "ingredient":
            item = next((ing for ing in recipe.ingredients if ing.id == target_id), None)
            return item.raw_text if item else target_id
        item = next((eq for eq in recipe.equipment if eq.id == target_id), None)
        return item.name if item else target_id


class TimerEditorDialog(QDialog):
    def __init__(self, existing=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit timer" if existing else "Add timer")
        self.label_input = QLineEdit(self)
        self.duration_input = QSpinBox(self)
        self.duration_input.setRange(1, 86_400)
        self.auto_start_input = QCheckBox(self)
        self.sound_input = QComboBox(self)
        for label, _key in SOUND_PRESET_CHOICES:
            self.sound_input.addItem(label)
        self.vibrate_input = QCheckBox("Vibrate when alerting", self)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Label", self.label_input)
        form.addRow("Duration (seconds)", self.duration_input)
        form.addRow("Start automatically with step", self.auto_start_input)
        form.addRow("Sound", self.sound_input)
        form.addRow("", self.vibrate_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing is not None:
            self.label_input.setText(existing.label)
            self.duration_input.setValue(existing.duration_seconds)
            self.auto_start_input.setChecked(existing.auto_start)
            self.sound_input.setCurrentText(label_for_sound_key(existing.alert_sound_key))
            self.vibrate_input.setChecked(existing.alert_vibrate)

    @property
    def label(self) -> str:
        return self.label_input.text().strip()

    @property
    def duration_seconds(self) -> int:
        return self.duration_input.value()

    @property
    def auto_start(self) -> bool:
        return self.auto_start_input.isChecked()

    @property
    def alert_sound_key(self) -> str | None:
        return sound_key_for_label(self.sound_input.currentText())

    @property
    def alert_vibrate(self) -> bool:
        return self.vibrate_input.isChecked()

