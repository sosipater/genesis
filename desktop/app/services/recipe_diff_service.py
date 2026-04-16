"""Deterministic structured recipe diffing based on stable IDs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from desktop.app.bundled_loader import BundledContentLoader
from desktop.app.domain.models import Recipe


class RecipeDiffService:
    def __init__(self, bundled_loader: BundledContentLoader | None = None):
        self._bundled_loader = bundled_loader

    def diff_recipes(self, old_recipe: Recipe, new_recipe: Recipe) -> dict[str, Any]:
        metadata_fields = [
            "title",
            "subtitle",
            "author",
            "source_name",
            "source_url",
            "category",
            "difficulty",
            "servings",
            "prep_minutes",
            "cook_minutes",
            "total_minutes",
            "status",
            "notes",
            "bundle_export_eligible",
            "export_bundle_recipe_id",
            "export_bundle_recipe_version",
            "origin_bundled_recipe_id",
            "origin_bundled_recipe_version",
            "is_forked_from_bundled",
        ]
        metadata_changes = self._diff_fields(old_recipe, new_recipe, metadata_fields)

        equipment_diff = self._diff_collection(
            old_recipe.equipment,
            new_recipe.equipment,
            id_field="id",
            field_names=[
                "name",
                "description",
                "why_used",
                "is_required",
                "notes",
                "affiliate_url",
                "alternate_equipment_text",
                "media_id",
                "display_order",
            ],
            order_field="display_order",
        )
        ingredient_diff = self._diff_collection(
            old_recipe.ingredients,
            new_recipe.ingredients,
            id_field="id",
            field_names=[
                "raw_text",
                "quantity_value",
                "quantity_text",
                "unit",
                "ingredient_name",
                "preparation_notes",
                "substitutions",
                "affiliate_url",
                "recommended_product",
                "media_id",
                "is_optional",
                "display_order",
            ],
            order_field="display_order",
        )
        step_diff = self._diff_collection(
            old_recipe.steps,
            new_recipe.steps,
            id_field="id",
            field_names=["title", "body_text", "step_type", "estimated_seconds", "media_id", "display_order"],
            order_field="display_order",
        )
        link_diff = self._diff_collection(
            old_recipe.step_links,
            new_recipe.step_links,
            id_field="id",
            field_names=["step_id", "target_type", "target_id", "token_key", "label_snapshot", "label_override"],
            order_field=None,
        )
        timer_diff = self._diff_timers(old_recipe, new_recipe)

        return {
            "old_recipe_id": old_recipe.id,
            "new_recipe_id": new_recipe.id,
            "recipe_metadata_changes": metadata_changes,
            "equipment": equipment_diff,
            "ingredients": ingredient_diff,
            "steps": step_diff,
            "step_links": link_diff,
            "step_timers": timer_diff,
            "summary": self._build_summary(
                metadata_changes,
                equipment_diff,
                ingredient_diff,
                step_diff,
                link_diff,
                timer_diff,
            ),
        }

    def diff_bundled_versions(self, bundled_v1: Recipe, bundled_v2: Recipe) -> dict[str, Any]:
        return self.diff_recipes(bundled_v1, bundled_v2)

    def diff_local_vs_origin(self, local_recipe: Recipe) -> dict[str, Any]:
        if not local_recipe.is_forked_from_bundled or not local_recipe.origin_bundled_recipe_id:
            raise ValueError("Recipe is not a forked local recipe with bundled origin metadata")
        if self._bundled_loader is None:
            raise ValueError("Bundled loader not configured for local vs origin diff")
        origin = next(
            (item for item in self._bundled_loader.load_bundled_recipes() if item.id == local_recipe.origin_bundled_recipe_id),
            None,
        )
        if origin is None:
            raise ValueError(f"Origin bundled recipe {local_recipe.origin_bundled_recipe_id} not found")
        diff = self.diff_recipes(origin, local_recipe)
        diff["origin_bundled_recipe_id"] = origin.id
        diff["origin_bundled_recipe_version"] = local_recipe.origin_bundled_recipe_version
        return diff

    def _diff_fields(self, old_obj: Any, new_obj: Any, field_names: list[str]) -> dict[str, dict[str, Any]]:
        changes: dict[str, dict[str, Any]] = {}
        for field in field_names:
            before = getattr(old_obj, field, None)
            after = getattr(new_obj, field, None)
            if before != after:
                changes[field] = {"before": before, "after": after}
        return dict(sorted(changes.items(), key=lambda item: item[0]))

    def _diff_collection(
        self,
        old_items: list[Any],
        new_items: list[Any],
        *,
        id_field: str,
        field_names: list[str],
        order_field: str | None,
    ) -> dict[str, Any]:
        old_map = {getattr(item, id_field): item for item in old_items}
        new_map = {getattr(item, id_field): item for item in new_items}
        old_ids = set(old_map.keys())
        new_ids = set(new_map.keys())

        added = [asdict(new_map[item_id]) for item_id in sorted(new_ids - old_ids)]
        removed = [asdict(old_map[item_id]) for item_id in sorted(old_ids - new_ids)]
        modified: list[dict[str, Any]] = []
        order_changes: list[dict[str, Any]] = []

        for item_id in sorted(old_ids & new_ids):
            old_item = old_map[item_id]
            new_item = new_map[item_id]
            field_changes = self._diff_fields(old_item, new_item, field_names)
            if field_changes:
                modified.append({"id": item_id, "fields": field_changes})
            if order_field is not None:
                old_order = getattr(old_item, order_field)
                new_order = getattr(new_item, order_field)
                if old_order != new_order:
                    order_changes.append({"id": item_id, "before": old_order, "after": new_order})

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "order_changed": bool(order_changes),
            "order_changes": order_changes,
        }

    def _diff_timers(self, old_recipe: Recipe, new_recipe: Recipe) -> dict[str, Any]:
        old_timers: dict[str, Any] = {}
        new_timers: dict[str, Any] = {}
        for step in old_recipe.steps:
            for timer in step.timers:
                old_timers[timer.id] = (step.id, timer)
        for step in new_recipe.steps:
            for timer in step.timers:
                new_timers[timer.id] = (step.id, timer)

        old_ids = set(old_timers.keys())
        new_ids = set(new_timers.keys())
        added = []
        removed = []
        modified = []
        for timer_id in sorted(new_ids - old_ids):
            step_id, timer = new_timers[timer_id]
            payload = asdict(timer)
            payload["step_id"] = step_id
            added.append(payload)
        for timer_id in sorted(old_ids - new_ids):
            step_id, timer = old_timers[timer_id]
            payload = asdict(timer)
            payload["step_id"] = step_id
            removed.append(payload)
        for timer_id in sorted(old_ids & new_ids):
            old_step_id, old_timer = old_timers[timer_id]
            new_step_id, new_timer = new_timers[timer_id]
            fields = self._diff_fields(
                old_timer,
                new_timer,
                ["label", "duration_seconds", "auto_start", "alert_sound_key"],
            )
            if old_step_id != new_step_id:
                fields["step_id"] = {"before": old_step_id, "after": new_step_id}
            if fields:
                modified.append({"id": timer_id, "fields": fields})
        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "order_changed": False,
            "order_changes": [],
        }

    def _build_summary(self, metadata: dict, *entity_diffs: dict) -> dict[str, Any]:
        added = sum(len(diff["added"]) for diff in entity_diffs)
        removed = sum(len(diff["removed"]) for diff in entity_diffs)
        modified = len(metadata) + sum(len(diff["modified"]) for diff in entity_diffs)
        order_changed = any(diff.get("order_changed", False) for diff in entity_diffs)
        return {
            "metadata_fields_changed": len(metadata),
            "entities_added": added,
            "entities_removed": removed,
            "entities_modified": modified,
            "order_changed": order_changed,
        }

