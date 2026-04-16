"""Portable local recipe share import/export service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator

from desktop.app.domain.models import Recipe, StepLink, StepTimer, RecipeEquipmentItem, RecipeIngredientItem, RecipeStep, utc_now_iso
from desktop.app.persistence.recipe_repository import RecipeRepository


USER_FACING_SHARE_MEDIA_BLOCKED = (
    "This recipe includes photos or other media. Sharing recipes with attachments is not supported yet, "
    "so export was stopped on purpose—your images would be left behind. Remove media from the recipe "
    "or duplicate it without images if you need a shareable file."
)


def user_facing_share_media_blocked_detail(*, recipe_id: str | None = None) -> str:
    prefix = f"Recipe {recipe_id}: " if recipe_id else ""
    return prefix + USER_FACING_SHARE_MEDIA_BLOCKED


@dataclass(slots=True)
class RecipeShareExportResult:
    package_path: Path
    recipe_count: int
    package_id: str


@dataclass(slots=True)
class RecipeShareImportResult:
    imported_count: int
    skipped_count: int
    collisions: list[str]
    errors: list[str]


class RecipeShareService:
    def __init__(self, repository: RecipeRepository, project_root: Path):
        self._repo = repository
        self._root = project_root
        self._recipe_schema = json.loads((self._root / "shared" / "schemas" / "recipe.schema.json").read_text(encoding="utf-8"))
        self._share_schema = json.loads(
            (self._root / "shared" / "schemas" / "recipe_share_package.schema.json").read_text(encoding="utf-8")
        )
        self._recipe_validator = Draft202012Validator(self._recipe_schema)
        self._share_validator = Draft202012Validator(self._share_schema)

    def export_recipes(self, recipe_ids: list[str], package_path: Path) -> RecipeShareExportResult:
        local_by_id = {recipe.id: recipe for recipe in self._repo.list_recipes(include_deleted=False) if recipe.scope == "local"}
        selected: list[Recipe] = []
        for recipe_id in recipe_ids:
            recipe = local_by_id.get(recipe_id)
            if recipe is None:
                raise ValueError(f"Recipe not found in local scope: {recipe_id}")
            if self._has_media_references(recipe):
                raise ValueError(user_facing_share_media_blocked_detail(recipe_id=recipe_id))
            selected.append(recipe)

        closure_ids = self._closure_local_dependency_ids([r.id for r in selected], local_by_id)
        to_export = [local_by_id[rid] for rid in closure_ids]
        for recipe in to_export:
            if self._has_media_references(recipe):
                raise ValueError(user_facing_share_media_blocked_detail(recipe_id=recipe.id))

        package_id = str(uuid4())
        payload = {
            "share_format_version": 1,
            "package_id": package_id,
            "exported_at_utc": utc_now_iso(),
            "source_app": "genesis-desktop",
            "media_included": False,
            "recipes": [recipe.to_dict() for recipe in sorted(to_export, key=lambda value: value.id)],
        }
        package_path.parent.mkdir(parents=True, exist_ok=True)
        package_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return RecipeShareExportResult(package_path=package_path, recipe_count=len(to_export), package_id=package_id)

    def import_package(self, package_path: Path, import_source_label: str | None = None) -> RecipeShareImportResult:
        payload = json.loads(package_path.read_text(encoding="utf-8"))
        errors = [error.message for error in self._share_validator.iter_errors(payload)]
        if errors:
            return RecipeShareImportResult(imported_count=0, skipped_count=0, collisions=[], errors=errors)

        package_id = payload["package_id"]
        imported_count = 0
        skipped_count = 0
        collisions: list[str] = []
        seen_import_keys: set[tuple[str, str]] = set()

        candidates: list[Recipe] = []
        for recipe_payload in payload["recipes"]:
            recipe_errors = [error.message for error in self._recipe_validator.iter_errors(recipe_payload)]
            if recipe_errors:
                errors.extend([f"recipe {recipe_payload.get('id', '<unknown>')}: {message}" for message in recipe_errors])
                skipped_count += 1
                continue
            try:
                imported_recipe = Recipe.from_dict(recipe_payload)
            except Exception as exc:
                errors.append(f"recipe {recipe_payload.get('id', '<unknown>')}: {exc}")
                skipped_count += 1
                continue
            if self._has_media_references(imported_recipe):
                errors.append(
                    f"recipe {recipe_payload.get('id', '<unknown>')}: {USER_FACING_SHARE_MEDIA_BLOCKED}"
                )
                skipped_count += 1
                continue

            import_key = (package_id, imported_recipe.id)
            if import_key in seen_import_keys:
                collisions.append(f"duplicate recipe id in package: {imported_recipe.id}")
                skipped_count += 1
                continue
            seen_import_keys.add(import_key)
            candidates.append(imported_recipe)

        package_recipe_ids = {recipe.id for recipe in candidates}
        orphan_errors: list[str] = []
        for recipe in candidates:
            for ing in recipe.ingredients:
                if ing.sub_recipe_id and ing.sub_recipe_id not in package_recipe_ids:
                    orphan_errors.append(
                        f"recipe {recipe.id}: ingredient line references sub-recipe {ing.sub_recipe_id} "
                        "which is not included in this share package"
                    )
        if orphan_errors:
            return RecipeShareImportResult(
                imported_count=0,
                skipped_count=skipped_count,
                collisions=collisions,
                errors=errors + orphan_errors,
            )

        recipe_id_map = {recipe.id: str(uuid4()) for recipe in sorted(candidates, key=lambda value: value.id)}
        for recipe in sorted(candidates, key=lambda value: value.id):
            existing = [
                row
                for row in self._repo.list_recipes(include_deleted=False)
                if row.imported_from_package_id == package_id and row.imported_from_recipe_id == recipe.id
            ]
            if existing:
                skipped_count += 1
                collisions.append(f"already imported from package: {recipe.id}")
                continue

            original_id = recipe.id
            imported_recipe = self._clone_with_recipe_id_map(recipe, recipe_id_map)
            imported_recipe.imported_from_package_id = package_id
            imported_recipe.imported_from_recipe_id = original_id
            imported_recipe.imported_at = utc_now_iso()
            imported_recipe.import_source_label = import_source_label or package_path.name
            imported_recipe.origin_bundled_recipe_id = None
            imported_recipe.origin_bundled_recipe_version = None
            imported_recipe.is_forked_from_bundled = False
            imported_recipe.bundled_content_version = None
            imported_recipe.bundle_export_eligible = False
            imported_recipe.scope = "local"
            imported_recipe.updated_at = utc_now_iso()
            imported_recipe.created_at = imported_recipe.updated_at

            try:
                self._repo.create_recipe(imported_recipe)
                imported_count += 1
            except Exception as exc:
                errors.append(f"recipe {original_id}: import failed: {exc}")
                skipped_count += 1

        return RecipeShareImportResult(
            imported_count=imported_count,
            skipped_count=skipped_count,
            collisions=collisions,
            errors=errors,
        )

    def _closure_local_dependency_ids(self, seed_ids: list[str], local_by_id: dict[str, Recipe]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        queue = list(seed_ids)
        while queue:
            rid = queue.pop(0)
            if rid in seen:
                continue
            recipe = local_by_id.get(rid)
            if recipe is None:
                raise ValueError(f"Recipe not found for export: {rid}")
            seen.add(rid)
            ordered.append(rid)
            for ing in sorted(recipe.ingredients, key=lambda row: row.display_order):
                if ing.sub_recipe_id and ing.sub_recipe_id not in seen:
                    queue.append(ing.sub_recipe_id)
        return sorted(ordered)

    def _clone_with_recipe_id_map(self, recipe: Recipe, recipe_id_map: dict[str, str]) -> Recipe:
        old_to_new: dict[str, str] = {}

        def _new_id(old_id: str) -> str:
            new_id = str(uuid4())
            old_to_new[old_id] = new_id
            return new_id

        cloned = Recipe(
            id=recipe_id_map[recipe.id],
            scope="local",
            title=recipe.title,
            status=recipe.status,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
            equipment=[],
            ingredients=[],
            steps=[],
            schema_version=recipe.schema_version,
            subtitle=recipe.subtitle,
            author=recipe.author,
            source_name=recipe.source_name,
            source_url=recipe.source_url,
            tags=list(recipe.tags),
            category=recipe.category,
            difficulty=recipe.difficulty,
            servings=recipe.servings,
            prep_minutes=recipe.prep_minutes,
            cook_minutes=recipe.cook_minutes,
            total_minutes=recipe.total_minutes,
            notes=recipe.notes,
            cover_media_id=recipe.cover_media_id,
            display_settings=dict(recipe.display_settings),
            step_links=[],
        )
        for item in recipe.equipment:
            cloned.equipment.append(
                RecipeEquipmentItem(
                    id=_new_id(item.id),
                    name=item.name,
                    is_required=item.is_required,
                    display_order=item.display_order,
                    description=item.description,
                    why_used=item.why_used,
                    notes=item.notes,
                    affiliate_url=item.affiliate_url,
                    alternate_equipment_text=item.alternate_equipment_text,
                    media_id=item.media_id,
                    global_equipment_id=item.global_equipment_id,
                )
            )
        for item in recipe.ingredients:
            new_sub: str | None = None
            if item.sub_recipe_id:
                new_sub = recipe_id_map.get(item.sub_recipe_id)
                if new_sub is None:
                    raise ValueError(f"sub-recipe id {item.sub_recipe_id} missing from import id map")
            cloned.ingredients.append(
                RecipeIngredientItem(
                    id=_new_id(item.id),
                    raw_text=item.raw_text,
                    is_optional=item.is_optional,
                    display_order=item.display_order,
                    quantity_value=item.quantity_value,
                    quantity_text=item.quantity_text,
                    unit=item.unit,
                    ingredient_name=item.ingredient_name,
                    preparation_notes=item.preparation_notes,
                    substitutions=item.substitutions,
                    affiliate_url=item.affiliate_url,
                    recommended_product=item.recommended_product,
                    media_id=item.media_id,
                    catalog_ingredient_id=item.catalog_ingredient_id,
                    sub_recipe_id=new_sub,
                    sub_recipe_usage_type=item.sub_recipe_usage_type,
                    sub_recipe_multiplier=item.sub_recipe_multiplier,
                    sub_recipe_display_name=item.sub_recipe_display_name,
                )
            )
        for step in recipe.steps:
            new_step_id = _new_id(step.id)
            cloned.steps.append(
                RecipeStep(
                    id=new_step_id,
                    body_text=step.body_text,
                    display_order=step.display_order,
                    step_type=step.step_type,
                    timers=[
                        StepTimer(
                            id=str(uuid4()),
                            label=timer.label,
                            duration_seconds=timer.duration_seconds,
                            auto_start=timer.auto_start,
                            alert_sound_key=timer.alert_sound_key,
                            alert_vibrate=timer.alert_vibrate,
                        )
                        for timer in step.timers
                    ],
                    title=step.title,
                    estimated_seconds=step.estimated_seconds,
                    media_id=step.media_id,
                )
            )
        for link in recipe.step_links:
            cloned.step_links.append(
                StepLink(
                    id=str(uuid4()),
                    step_id=old_to_new.get(link.step_id, link.step_id),
                    target_type=link.target_type,
                    target_id=old_to_new.get(link.target_id, link.target_id),
                    token_key=link.token_key,
                    label_snapshot=link.label_snapshot,
                    label_override=link.label_override,
                )
            )
        return cloned

    def _has_media_references(self, recipe: Recipe) -> bool:
        if recipe.cover_media_id:
            return True
        for item in recipe.equipment:
            if item.media_id:
                return True
        for item in recipe.ingredients:
            if item.media_id:
                return True
        for step in recipe.steps:
            if step.media_id:
                return True
        return False
