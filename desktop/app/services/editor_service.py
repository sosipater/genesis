"""Editor orchestration service for local and bundled recipes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

from desktop.app.bundled_loader import BundledContentLoader
from desktop.app.domain.models import (
    Recipe,
    RecipeEquipmentItem,
    RecipeIngredientItem,
    RecipeStep,
    StepLink,
    StepTimer,
    utc_now_iso,
)
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.runtime_paths import RuntimePaths, build_runtime_paths
from desktop.app.services.backup_service import BackupService
from desktop.app.services.bundle_export_service import BundleExportResult, BundleExportService
from desktop.app.services.diagnostics_service import DiagnosticsService
from desktop.app.services.meal_plan_service import MealPlanService
from desktop.app.services.media_service import MediaService
from desktop.app.services.recipe_diff_service import RecipeDiffService
from desktop.app.services.recipe_share_service import RecipeShareExportResult, RecipeShareImportResult, RecipeShareService
from desktop.app.services.recipe_search_service import RecipeSearchFilters, RecipeSearchService
from desktop.app.versioning import SYNC_PROTOCOL_VERSION


RecipeSource = Literal["local", "bundled"]


@dataclass(slots=True)
class LibraryRecipeItem:
    id: str
    title: str
    subtitle: str | None
    source: RecipeSource
    status: str
    bundle_export_eligible: bool = False
    is_forked_from_bundled: bool = False
    is_favorite: bool = False
    last_opened_at: str | None = None
    last_cooked_at: str | None = None


@dataclass(slots=True)
class HomeMealEntry:
    date: str
    meal_plan_id: str
    meal_plan_name: str
    meal_slot: str | None
    slot_label: str | None
    recipe_id: str
    recipe_title: str


@dataclass(slots=True)
class HomeOverview:
    today: list[HomeMealEntry]
    this_week: dict[str, list[HomeMealEntry]]
    quick_recent_recipe_id: str | None
    quick_recent_recipe_title: str | None
    quick_latest_grocery_id: str | None
    quick_latest_grocery_name: str | None
    quick_active_meal_plan_id: str | None
    quick_active_meal_plan_name: str | None


class EditorService:
    def __init__(
        self,
        repository: RecipeRepository,
        bundled_loader: BundledContentLoader,
        project_root: Path,
        runtime_paths: RuntimePaths | None = None,
        schema_version: int = 0,
        sync_protocol_version: int = SYNC_PROTOCOL_VERSION,
    ):
        runtime_paths = runtime_paths or build_runtime_paths(project_root)
        self._repository = repository
        self._bundled_loader = bundled_loader
        self._bundle_export_service = BundleExportService(repository, project_root)
        self._diff_service = RecipeDiffService(bundled_loader)
        self._search_service = RecipeSearchService()
        self._meal_plan_service = MealPlanService(repository)
        self._media_service = MediaService(repository, runtime_paths.media_root)
        self._share_service = RecipeShareService(repository, project_root)
        self._backup_service = BackupService(runtime_paths, schema_version=schema_version, sync_protocol_version=sync_protocol_version)
        self._diagnostics_service = DiagnosticsService(
            repository,
            runtime_paths=runtime_paths,
            media_service=self._media_service,
            schema_version=schema_version,
            sync_protocol_version=sync_protocol_version,
        )

    def list_library_items(self) -> list[LibraryRecipeItem]:
        state_by_recipe = {row["recipe_id"]: row for row in self._list_user_states()}
        local_items = [
            LibraryRecipeItem(
                id=recipe.id,
                title=recipe.title,
                subtitle=recipe.subtitle,
                source="local",
                status=recipe.status,
                bundle_export_eligible=recipe.bundle_export_eligible,
                is_forked_from_bundled=recipe.is_forked_from_bundled,
                is_favorite=bool(state_by_recipe.get(recipe.id, {}).get("is_favorite", False)),
                last_opened_at=state_by_recipe.get(recipe.id, {}).get("last_opened_at"),
                last_cooked_at=state_by_recipe.get(recipe.id, {}).get("last_cooked_at"),
            )
            for recipe in self._repository.list_recipes(include_deleted=False)
        ]
        bundled_items = [
            LibraryRecipeItem(
                id=recipe.id,
                title=recipe.title,
                subtitle=recipe.subtitle,
                source="bundled",
                status=recipe.status,
                bundle_export_eligible=False,
                is_forked_from_bundled=False,
                is_favorite=bool(state_by_recipe.get(recipe.id, {}).get("is_favorite", False)),
                last_opened_at=state_by_recipe.get(recipe.id, {}).get("last_opened_at"),
                last_cooked_at=state_by_recipe.get(recipe.id, {}).get("last_cooked_at"),
            )
            for recipe in self._bundled_loader.load_bundled_recipes()
            if recipe.deleted_at is None
        ]
        return sorted(local_items, key=lambda item: item.title.lower()) + sorted(
            bundled_items, key=lambda item: item.title.lower()
        )

    def load_recipe(self, recipe_id: str, source: RecipeSource) -> tuple[Recipe | None, bool]:
        if source == "local":
            recipe = self._repository.get_recipe_by_id(recipe_id)
            self._repository.upsert_recipe_user_state(recipe_id, mark_opened=True)
            return recipe, False
        for recipe in self._bundled_loader.load_bundled_recipes():
            if recipe.id == recipe_id:
                self._repository.upsert_recipe_user_state(recipe_id, mark_opened=True)
                return recipe, True
        return None, True

    def create_new_local_recipe(self) -> Recipe:
        now = utc_now_iso()
        return Recipe(
            id=str(uuid4()),
            scope="local",
            title="Untitled Recipe",
            status="draft",
            created_at=now,
            updated_at=now,
            equipment=[],
            ingredients=[],
            steps=[],
            tags=[],
            step_links=[],
        )

    def save_recipe(self, recipe: Recipe) -> None:
        recipe.scope = "local"
        recipe.updated_at = utc_now_iso()
        existing = self._repository.get_recipe_by_id(recipe.id)
        if existing is None:
            if not recipe.created_at:
                recipe.created_at = recipe.updated_at
            self._repository.create_recipe(recipe)
        else:
            recipe.created_at = existing.created_at
            self._repository.update_recipe(recipe)

    def attach_cover_media(self, recipe: Recipe, source_path: Path) -> dict:
        asset = self._media_service.import_for_owner("recipe_cover", recipe.id, source_path)
        recipe.cover_media_id = asset["id"]
        return asset

    def remove_cover_media(self, recipe: Recipe) -> None:
        if recipe.cover_media_id:
            self._media_service.remove_media(recipe.cover_media_id)
            recipe.cover_media_id = None

    def attach_step_media(self, recipe: Recipe, step_id: str, source_path: Path) -> dict:
        asset = self._media_service.import_for_owner("step", step_id, source_path)
        for step in recipe.steps:
            if step.id == step_id:
                step.media_id = asset["id"]
                return asset
        raise ValueError(f"Step not found: {step_id}")

    def remove_step_media(self, recipe: Recipe, step_id: str) -> None:
        for step in recipe.steps:
            if step.id == step_id:
                if step.media_id:
                    self._media_service.remove_media(step.media_id)
                step.media_id = None
                return
        raise ValueError(f"Step not found: {step_id}")

    def attach_ingredient_media(self, recipe: Recipe, ingredient_id: str, source_path: Path) -> dict:
        asset = self._media_service.import_for_owner("ingredient", ingredient_id, source_path)
        for item in recipe.ingredients:
            if item.id == ingredient_id:
                item.media_id = asset["id"]
                return asset
        raise ValueError(f"Ingredient not found: {ingredient_id}")

    def remove_ingredient_media(self, recipe: Recipe, ingredient_id: str) -> None:
        for item in recipe.ingredients:
            if item.id == ingredient_id:
                if item.media_id:
                    self._media_service.remove_media(item.media_id)
                item.media_id = None
                return
        raise ValueError(f"Ingredient not found: {ingredient_id}")

    def attach_equipment_media(self, recipe: Recipe, equipment_id: str, source_path: Path) -> dict:
        asset = self._media_service.import_for_owner("equipment", equipment_id, source_path)
        for item in recipe.equipment:
            if item.id == equipment_id:
                item.media_id = asset["id"]
                return asset
        raise ValueError(f"Equipment not found: {equipment_id}")

    def remove_equipment_media(self, recipe: Recipe, equipment_id: str) -> None:
        for item in recipe.equipment:
            if item.id == equipment_id:
                if item.media_id:
                    self._media_service.remove_media(item.media_id)
                item.media_id = None
                return
        raise ValueError(f"Equipment not found: {equipment_id}")

    def resolve_media_path(self, media_asset_id: str) -> Path | None:
        return self._media_service.resolve_media_path(media_asset_id)

    def media_health_report(self) -> dict:
        return self._media_service.scan_health()

    def cleanup_orphan_media(self, orphan_ids: list[str]) -> dict:
        return self._media_service.cleanup_orphan_assets(orphan_ids)

    def duplicate_bundled_to_local(self, bundled_recipe_id: str) -> Recipe:
        bundled, is_read_only = self.load_recipe(bundled_recipe_id, source="bundled")
        if bundled is None or not is_read_only:
            raise ValueError(f"Bundled recipe {bundled_recipe_id} not found")
        return self._clone_recipe_as_local(bundled)

    def export_eligible_bundled_content(self, content_version: str) -> BundleExportResult:
        return self._bundle_export_service.export_eligible(content_version)

    def compare_local_with_origin(self, local_recipe: Recipe) -> dict:
        return self._diff_service.diff_local_vs_origin(local_recipe)

    def list_tag_names(self) -> list[str]:
        return [str(row["name"]) for row in self._repository.list_tags_for_picker()]

    def list_global_equipment_summaries(self) -> list[dict[str, str | None]]:
        return [
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "notes": row["notes"],
                "media_id": row["media_id"],
            }
            for row in self._repository.list_global_equipment_for_picker()
        ]

    def create_global_equipment_record(
        self, name: str, *, notes: str | None = None, media_id: str | None = None
    ) -> str:
        return self._repository.create_global_equipment(name, notes=notes, media_id=media_id)

    def search_library(self, query: str, filters: RecipeSearchFilters | None = None) -> list[LibraryRecipeItem]:
        state_by_recipe = {row["recipe_id"]: row for row in self._list_user_states()}
        all_recipes = self._repository.list_recipes(include_deleted=False) + [
            item for item in self._bundled_loader.load_bundled_recipes() if item.deleted_at is None
        ]
        results = self._search_service.search(all_recipes, query, filters)
        return [
            LibraryRecipeItem(
                id=result.recipe.id,
                title=result.recipe.title,
                subtitle=result.recipe.subtitle,
                source="local" if result.recipe.scope == "local" else "bundled",
                status=result.recipe.status,
                bundle_export_eligible=result.recipe.bundle_export_eligible,
                is_forked_from_bundled=result.recipe.is_forked_from_bundled,
                is_favorite=bool(state_by_recipe.get(result.recipe.id, {}).get("is_favorite", False)),
                last_opened_at=state_by_recipe.get(result.recipe.id, {}).get("last_opened_at"),
                last_cooked_at=state_by_recipe.get(result.recipe.id, {}).get("last_cooked_at"),
            )
            for result in results
        ]

    def set_favorite(self, recipe_id: str, is_favorite: bool) -> None:
        self._repository.upsert_recipe_user_state(recipe_id, is_favorite=is_favorite)

    def mark_cooked(self, recipe_id: str) -> None:
        self._repository.upsert_recipe_user_state(recipe_id, mark_cooked=True)

    def list_favorite_recipes(self) -> list[Recipe]:
        return self._repository.list_recipes_by_ids(self._repository.list_favorite_recipe_ids())

    def list_recent_opened_recipes(self, limit: int = 20) -> list[Recipe]:
        return self._repository.list_recipes_by_ids(self._repository.list_recently_opened_recipe_ids(limit=limit))

    def list_recent_cooked_recipes(self, limit: int = 20) -> list[Recipe]:
        return self._repository.list_recipes_by_ids(self._repository.list_recently_cooked_recipe_ids(limit=limit))

    def _list_user_states(self) -> list[dict]:
        recipe_ids = [r.id for r in self._repository.list_recipes(include_deleted=False)]
        states = []
        for recipe_id in recipe_ids:
            row = self._repository.get_recipe_user_state(recipe_id)
            if row:
                states.append(row)
        return states

    def get_home_overview(self, today_date: str | None = None) -> HomeOverview:
        today = date.fromisoformat(today_date) if today_date else date.today()
        week_start = today - timedelta(days=(today.weekday() - 0) % 7)
        week_end = week_start + timedelta(days=6)
        recipe_title_by_id = {item.id: item.title for item in self.list_library_items() if item.source == "local"}
        plans = self._repository.list_meal_plans()
        scheduled: list[HomeMealEntry] = []
        for plan in plans:
            for item in self._repository.list_meal_plan_items(plan["id"]):
                planned_date = item.get("planned_date")
                if not planned_date:
                    continue
                recipe_id = item["recipe_id"]
                scheduled.append(
                    HomeMealEntry(
                        date=planned_date,
                        meal_plan_id=plan["id"],
                        meal_plan_name=plan["name"],
                        meal_slot=item.get("meal_slot"),
                        slot_label=item.get("slot_label"),
                        recipe_id=recipe_id,
                        recipe_title=recipe_title_by_id.get(recipe_id, recipe_id),
                    )
                )
        scheduled.sort(
            key=lambda row: (
                row.date,
                self._slot_order(row.meal_slot),
                row.recipe_title.lower(),
            )
        )
        today_key = today.isoformat()
        today_entries = [entry for entry in scheduled if entry.date == today_key]
        week_entries = [entry for entry in scheduled if week_start.isoformat() <= entry.date <= week_end.isoformat()]
        week_grouped: dict[str, list[HomeMealEntry]] = {}
        for entry in week_entries:
            week_grouped.setdefault(entry.date, []).append(entry)

        recent_recipe_title = None
        recent_recipe_id = None
        recent_opened = self.list_recent_opened_recipes(limit=1)
        if recent_opened:
            recent_recipe_id = recent_opened[0].id
            recent_recipe_title = recent_opened[0].title

        grocery_lists = self.list_grocery_lists()
        latest_grocery = grocery_lists[0] if grocery_lists else None
        active_plan = plans[0] if plans else None
        return HomeOverview(
            today=today_entries,
            this_week=dict(sorted(week_grouped.items(), key=lambda kv: kv[0])),
            quick_recent_recipe_id=recent_recipe_id,
            quick_recent_recipe_title=recent_recipe_title,
            quick_latest_grocery_id=(latest_grocery["id"] if latest_grocery else None),
            quick_latest_grocery_name=(latest_grocery["name"] if latest_grocery else None),
            quick_active_meal_plan_id=(active_plan["id"] if active_plan else None),
            quick_active_meal_plan_name=(active_plan["name"] if active_plan else None),
        )

    def create_collection(self, name: str) -> str:
        return self._repository.create_collection(name)

    def rename_collection(self, collection_id: str, name: str) -> None:
        self._repository.rename_collection(collection_id, name)

    def delete_collection(self, collection_id: str) -> None:
        self._repository.delete_collection(collection_id)

    def list_collections(self) -> list[dict]:
        return self._repository.list_collections()

    def add_recipe_to_collection(self, collection_id: str, recipe_id: str) -> None:
        self._repository.add_recipe_to_collection(collection_id, recipe_id)

    def remove_recipe_from_collection(self, collection_id: str, recipe_id: str) -> None:
        self._repository.remove_recipe_from_collection(collection_id, recipe_id)

    def list_collection_recipes(self, collection_id: str) -> list[Recipe]:
        ids = self._repository.list_collection_recipe_ids(collection_id)
        return self._repository.list_recipes_by_ids(ids)

    def add_recipe_to_working_set(self, recipe_id: str) -> None:
        self._repository.add_to_working_set(recipe_id)

    def remove_recipe_from_working_set(self, recipe_id: str) -> None:
        self._repository.remove_from_working_set(recipe_id)

    def list_working_set_recipes(self) -> list[Recipe]:
        ids = self._repository.list_working_set_recipe_ids()
        return self._repository.list_recipes_by_ids(ids)

    def create_meal_plan(self, name: str, start_date: str | None = None, end_date: str | None = None) -> str:
        return self._repository.create_meal_plan(name, start_date, end_date)

    def list_meal_plans(self) -> list[dict]:
        return self._repository.list_meal_plans()

    def delete_meal_plan(self, meal_plan_id: str) -> None:
        self._repository.delete_meal_plan(meal_plan_id)

    def restore_meal_plan(self, meal_plan_id: str) -> None:
        self._repository.restore_meal_plan(meal_plan_id)

    def add_meal_plan_item(
        self,
        meal_plan_id: str,
        recipe_id: str,
        servings_override: float | None = None,
        notes: str | None = None,
        planned_date: str | None = None,
        meal_slot: str | None = None,
        slot_label: str | None = None,
        sort_order: int = 0,
    ) -> str:
        return self._repository.add_meal_plan_item(
            meal_plan_id,
            recipe_id,
            servings_override,
            notes,
            planned_date=planned_date,
            meal_slot=meal_slot,
            slot_label=slot_label,
            sort_order=sort_order,
        )

    def remove_meal_plan_item(self, meal_plan_item_id: str) -> None:
        self._repository.remove_meal_plan_item(meal_plan_item_id)

    def list_meal_plan_items(self, meal_plan_id: str) -> list[dict]:
        return self._repository.list_meal_plan_items(meal_plan_id)

    def update_meal_plan_item_schedule(
        self,
        meal_plan_item_id: str,
        *,
        planned_date: str | None,
        meal_slot: str | None,
        slot_label: str | None,
        sort_order: int | None = None,
    ) -> None:
        self._repository.update_meal_plan_item_schedule(
            meal_plan_item_id,
            planned_date=planned_date,
            meal_slot=meal_slot,
            slot_label=slot_label,
            sort_order=sort_order,
        )

    def generate_grocery_list_from_meal_plan(
        self, meal_plan_id: str, *, start_date: str | None = None, end_date: str | None = None
    ) -> str:
        plan_items = self._repository.list_meal_plan_items(meal_plan_id)
        if start_date or end_date:
            plan_items = [
                item
                for item in plan_items
                if item.get("planned_date")
                and (start_date is None or item["planned_date"] >= start_date)
                and (end_date is None or item["planned_date"] <= end_date)
            ]
        recipes_with_factors: list[tuple[Recipe, float]] = []
        for item in plan_items:
            recipe = self._repository.get_recipe_by_id(item["recipe_id"])
            if recipe is None:
                continue
            if recipe.servings and item.get("servings_override"):
                factor = float(item["servings_override"]) / float(recipe.servings)
            else:
                factor = 1.0
            recipes_with_factors.append((recipe, factor))
        grocery_items = self._meal_plan_service.generate_grocery_items(recipes_with_factors)
        name_suffix = f"{start_date or '?'}..{end_date or start_date}" if (start_date or end_date) else utc_now_iso()[:10]
        list_id = self._repository.create_grocery_list(meal_plan_id=meal_plan_id, name=f"Grocery {name_suffix}")
        self._repository.replace_grocery_list_items(
            list_id,
            [
                {
                    "name": item.name,
                    "quantity_value": item.quantity_value,
                    "unit": item.unit,
                    "checked": False,
                    "source_recipe_ids": item.source_recipe_ids,
                    "source_type": "generated",
                    "generated_group_key": item.generated_group_key,
                    "was_user_modified": False,
                }
                for item in grocery_items
            ],
        )
        return list_id

    def regenerate_grocery_list_snapshot(self, meal_plan_id: str) -> str:
        # Explicitly create a new snapshot; existing lists remain unchanged.
        return self.generate_grocery_list_from_meal_plan(meal_plan_id)

    def generate_weekly_grocery_snapshot(self, meal_plan_id: str, week_start_date: str) -> str:
        from datetime import date, timedelta

        start = date.fromisoformat(week_start_date)
        end = start + timedelta(days=6)
        return self.generate_grocery_list_from_meal_plan(
            meal_plan_id,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )

    def list_meal_plan_items_grouped_by_date(self, meal_plan_id: str) -> dict[str, list[dict]]:
        items = self._repository.list_meal_plan_items(meal_plan_id)
        grouped: dict[str, list[dict]] = {}
        for item in items:
            key = item.get("planned_date") or "unassigned"
            grouped.setdefault(key, []).append(item)
        for key in grouped:
            grouped[key].sort(key=lambda row: (row.get("meal_slot") or "zzz", int(row.get("sort_order", 0))))
        return dict(sorted(grouped.items(), key=lambda kv: kv[0]))

    def list_grocery_lists(self) -> list[dict]:
        return self._repository.list_grocery_lists()

    def list_grocery_list_items(self, grocery_list_id: str) -> list[dict]:
        return self._repository.list_grocery_list_items(grocery_list_id)

    def toggle_grocery_item_checked(self, grocery_item_id: str, checked: bool) -> None:
        self._repository.toggle_grocery_item_checked(grocery_item_id, checked)

    def add_manual_grocery_item(
        self,
        grocery_list_id: str,
        name: str,
        quantity_value: float | None = None,
        unit: str | None = None,
    ) -> str:
        return self._repository.add_manual_grocery_item(grocery_list_id, name, quantity_value, unit)

    def update_grocery_item(self, grocery_item_id: str, *, name: str, quantity_value: float | None, unit: str | None) -> None:
        self._repository.update_grocery_item(grocery_item_id, name=name, quantity_value=quantity_value, unit=unit)

    def delete_grocery_item(self, grocery_item_id: str) -> None:
        self._repository.delete_grocery_item(grocery_item_id)

    def reorder_grocery_items(self, grocery_list_id: str, ordered_item_ids: list[str]) -> None:
        self._repository.reorder_grocery_items(grocery_list_id, ordered_item_ids)

    def export_recipe_share(self, recipe_ids: list[str], package_path: Path) -> RecipeShareExportResult:
        return self._share_service.export_recipes(recipe_ids, package_path)

    def import_recipe_share(self, package_path: Path, import_source_label: str | None = None) -> RecipeShareImportResult:
        return self._share_service.import_package(package_path, import_source_label)

    def create_backup(self, backup_path: Path) -> dict:
        result = self._backup_service.create_backup(backup_path)
        return {"path": str(result.backup_path), "file_count": result.file_count, "total_bytes": result.total_bytes}

    def validate_backup(self, backup_path: Path) -> dict:
        return self._backup_service.validate_backup(backup_path)

    def restore_backup(self, backup_path: Path, *, allow_replace: bool) -> dict:
        return self._backup_service.restore_backup(backup_path, allow_replace=allow_replace)

    def diagnostics_report(self) -> dict:
        return self._diagnostics_service.full_report()

    def diagnostics_text(self) -> str:
        return self._diagnostics_service.format_report(self._diagnostics_service.full_report())

    def _clone_recipe_as_local(self, bundled: Recipe) -> Recipe:
        now = utc_now_iso()
        old_to_new_ids: dict[str, str] = {}

        def new_id(old_id: str) -> str:
            generated = str(uuid4())
            old_to_new_ids[old_id] = generated
            return generated

        cloned = Recipe(
            id=str(uuid4()),
            scope="local",
            title=f"{bundled.title} (Copy)",
            status="draft",
            created_at=now,
            updated_at=now,
            equipment=[],
            ingredients=[],
            steps=[],
            subtitle=bundled.subtitle,
            author=bundled.author,
            source_name=bundled.source_name,
            source_url=bundled.source_url,
            tags=list(bundled.tags),
            category=bundled.category,
            difficulty=bundled.difficulty,
            servings=bundled.servings,
            prep_minutes=bundled.prep_minutes,
            cook_minutes=bundled.cook_minutes,
            total_minutes=bundled.total_minutes,
            notes=bundled.notes,
            step_links=[],
            origin_bundled_recipe_id=bundled.id,
            origin_bundled_recipe_version=bundled.export_bundle_recipe_version,
            is_forked_from_bundled=True,
        )

        for item in bundled.equipment:
            cloned.equipment.append(
                RecipeEquipmentItem(
                    id=new_id(item.id),
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

        for item in bundled.ingredients:
            cloned.ingredients.append(
                RecipeIngredientItem(
                    id=new_id(item.id),
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
                )
            )

        for step in bundled.steps:
            step_id = new_id(step.id)
            cloned.steps.append(
                RecipeStep(
                    id=step_id,
                    body_text=step.body_text,
                    display_order=step.display_order,
                    step_type=step.step_type,
                    title=step.title,
                    estimated_seconds=step.estimated_seconds,
                    media_id=step.media_id,
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
                )
            )

        for link in bundled.step_links:
            new_step_id = old_to_new_ids.get(link.step_id, link.step_id)
            new_target_id = old_to_new_ids.get(link.target_id, link.target_id)
            cloned.step_links.append(
                StepLink(
                    id=str(uuid4()),
                    step_id=new_step_id,
                    target_type=link.target_type,
                    target_id=new_target_id,
                    token_key=link.token_key,
                    label_snapshot=link.label_snapshot,
                    label_override=link.label_override,
                )
            )
        return cloned

    def _slot_order(self, slot: str | None) -> int:
        order = {
            "breakfast": 0,
            "lunch": 1,
            "dinner": 2,
            "snack": 3,
            "custom": 4,
        }
        return order.get(slot or "", 5)

