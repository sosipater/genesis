"""Editor state model with explicit dirty/read-only behavior."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EditorState:
    current_recipe_id: str | None = None
    current_scope: str | None = None
    is_dirty: bool = False
    is_read_only: bool = False

    @property
    def can_save(self) -> bool:
        return (not self.is_read_only) and self.is_dirty and self.current_recipe_id is not None

    def open_recipe(self, recipe_id: str, scope: str, is_read_only: bool) -> None:
        self.current_recipe_id = recipe_id
        self.current_scope = scope
        self.is_read_only = is_read_only
        self.is_dirty = False

    def mark_dirty(self) -> None:
        if not self.is_read_only:
            self.is_dirty = True

    def mark_clean(self) -> None:
        self.is_dirty = False

