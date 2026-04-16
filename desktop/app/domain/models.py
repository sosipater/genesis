"""Typed domain entities for Genesis desktop foundation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID


RecipeScope = Literal["bundled", "local"]
RecipeStatus = Literal["draft", "published", "archived"]
StepType = Literal["instruction", "note", "section_break"]
LinkTargetType = Literal["ingredient", "equipment"]


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_uuid(value: str, field_name: str) -> None:
    try:
        UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid UUID") from exc


@dataclass(slots=True)
class RecipeEquipmentItem:
    id: str
    name: str
    is_required: bool
    display_order: int
    description: str | None = None
    why_used: str | None = None
    notes: str | None = None
    affiliate_url: str | None = None
    alternate_equipment_text: str | None = None
    media_id: str | None = None
    global_equipment_id: str | None = None

    def validate(self) -> None:
        _require_uuid(self.id, "equipment.id")
        if not self.name.strip():
            raise ValueError("equipment.name cannot be empty")
        if self.display_order < 0:
            raise ValueError("equipment.display_order must be >= 0")
        if self.global_equipment_id is not None:
            _require_uuid(self.global_equipment_id, "equipment.global_equipment_id")


@dataclass(slots=True)
class RecipeIngredientItem:
    id: str
    raw_text: str
    is_optional: bool
    display_order: int
    quantity_value: float | None = None
    quantity_text: str | None = None
    unit: str | None = None
    ingredient_name: str | None = None
    preparation_notes: str | None = None
    substitutions: str | None = None
    affiliate_url: str | None = None
    recommended_product: str | None = None
    media_id: str | None = None

    def validate(self) -> None:
        _require_uuid(self.id, "ingredient.id")
        if not self.raw_text.strip():
            raise ValueError("ingredient.raw_text cannot be empty")
        if self.display_order < 0:
            raise ValueError("ingredient.display_order must be >= 0")
        if self.quantity_value is not None and self.quantity_value < 0:
            raise ValueError("ingredient.quantity_value must be >= 0")


@dataclass(slots=True)
class StepTimer:
    id: str
    label: str
    duration_seconds: int
    auto_start: bool
    alert_sound_key: str | None = None
    alert_vibrate: bool = False

    def validate(self) -> None:
        _require_uuid(self.id, "timer.id")
        if not self.label.strip():
            raise ValueError("timer.label cannot be empty")
        if self.duration_seconds <= 0:
            raise ValueError("timer.duration_seconds must be > 0")


@dataclass(slots=True)
class RecipeStep:
    id: str
    body_text: str
    display_order: int
    step_type: StepType
    timers: list[StepTimer] = field(default_factory=list)
    title: str | None = None
    estimated_seconds: int | None = None
    media_id: str | None = None

    def validate(self) -> None:
        _require_uuid(self.id, "step.id")
        if not self.body_text.strip():
            raise ValueError("step.body_text cannot be empty")
        if self.display_order < 0:
            raise ValueError("step.display_order must be >= 0")
        if self.estimated_seconds is not None and self.estimated_seconds < 0:
            raise ValueError("step.estimated_seconds must be >= 0")
        for timer in self.timers:
            timer.validate()


@dataclass(slots=True)
class StepLink:
    id: str
    step_id: str
    target_type: LinkTargetType
    target_id: str
    token_key: str
    label_snapshot: str
    label_override: str | None = None

    def validate(self) -> None:
        _require_uuid(self.id, "step_link.id")
        _require_uuid(self.step_id, "step_link.step_id")
        _require_uuid(self.target_id, "step_link.target_id")
        if not self.token_key.strip():
            raise ValueError("step_link.token_key cannot be empty")
        if not self.label_snapshot.strip():
            raise ValueError("step_link.label_snapshot cannot be empty")


@dataclass(slots=True)
class MediaAsset:
    id: str
    owner_type: str
    owner_id: str
    mime_type: str
    file_name: str | None = None
    relative_path: str | None = None
    local_path: str | None = None
    bundled_path: str | None = None
    width: int | None = None
    height: int | None = None
    checksum_sha256: str | None = None


@dataclass(slots=True)
class SyncState:
    entity_type: str
    entity_id: str
    entity_updated_at: str
    last_modified_device_id: str
    last_synced_at: str | None
    sync_version: int
    is_tombstone: bool


@dataclass(slots=True)
class Recipe:
    id: str
    scope: RecipeScope
    title: str
    status: RecipeStatus
    created_at: str
    updated_at: str
    equipment: list[RecipeEquipmentItem]
    ingredients: list[RecipeIngredientItem]
    steps: list[RecipeStep]
    schema_version: int = 1
    bundled_content_version: str | None = None
    bundle_export_eligible: bool = False
    export_bundle_recipe_id: str | None = None
    export_bundle_recipe_version: int = 1
    origin_bundled_recipe_id: str | None = None
    origin_bundled_recipe_version: int | None = None
    is_forked_from_bundled: bool = False
    imported_from_package_id: str | None = None
    imported_from_recipe_id: str | None = None
    imported_at: str | None = None
    import_source_label: str | None = None
    subtitle: str | None = None
    author: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    difficulty: str | None = None
    servings: float | None = None
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    total_minutes: int | None = None
    notes: str | None = None
    cover_media_id: str | None = None
    display_settings: dict[str, Any] = field(default_factory=dict)
    deleted_at: str | None = None
    step_links: list[StepLink] = field(default_factory=list)

    def validate(self) -> None:
        _require_uuid(self.id, "recipe.id")
        if not self.title.strip():
            raise ValueError("recipe.title cannot be empty")
        if self.scope not in ("bundled", "local"):
            raise ValueError("recipe.scope must be bundled/local")
        if self.scope == "bundled" and not self.bundled_content_version:
            raise ValueError("bundled recipes must include bundled_content_version")
        if self.export_bundle_recipe_id is not None:
            _require_uuid(self.export_bundle_recipe_id, "recipe.export_bundle_recipe_id")
        if self.origin_bundled_recipe_id is not None:
            _require_uuid(self.origin_bundled_recipe_id, "recipe.origin_bundled_recipe_id")
        if self.imported_from_recipe_id is not None:
            _require_uuid(self.imported_from_recipe_id, "recipe.imported_from_recipe_id")
        if self.export_bundle_recipe_version < 1:
            raise ValueError("recipe.export_bundle_recipe_version must be >= 1")
        for item in self.equipment:
            item.validate()
        for item in self.ingredients:
            item.validate()
        for step in self.steps:
            step.validate()
        for link in self.step_links:
            link.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Recipe":
        return cls(
            id=payload["id"],
            scope=payload["scope"],
            title=payload["title"],
            status=payload["status"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            equipment=[
                RecipeEquipmentItem(
                    id=item["id"],
                    name=item["name"],
                    is_required=item["is_required"],
                    display_order=item["display_order"],
                    description=item.get("description"),
                    why_used=item.get("why_used"),
                    notes=item.get("notes"),
                    affiliate_url=item.get("affiliate_url"),
                    alternate_equipment_text=item.get("alternate_equipment_text"),
                    media_id=item.get("media_id"),
                    global_equipment_id=item.get("global_equipment_id"),
                )
                for item in payload.get("equipment", [])
            ],
            ingredients=[RecipeIngredientItem(**item) for item in payload.get("ingredients", [])],
            steps=[
                RecipeStep(
                    **{
                        **{k: v for k, v in item.items() if k != "timers"},
                        "timers": [
                            StepTimer(
                                id=t["id"],
                                label=t["label"],
                                duration_seconds=t["duration_seconds"],
                                auto_start=t["auto_start"],
                                alert_sound_key=t.get("alert_sound_key"),
                                alert_vibrate=bool(t.get("alert_vibrate", False)),
                            )
                            for t in item.get("timers", [])
                        ],
                    }
                )
                for item in payload.get("steps", [])
            ],
            schema_version=payload.get("schema_version", 1),
            bundled_content_version=payload.get("bundled_content_version"),
            bundle_export_eligible=payload.get("bundle_export_eligible", False),
            export_bundle_recipe_id=payload.get("export_bundle_recipe_id"),
            export_bundle_recipe_version=payload.get("export_bundle_recipe_version", 1),
            origin_bundled_recipe_id=payload.get("origin_bundled_recipe_id"),
            origin_bundled_recipe_version=payload.get("origin_bundled_recipe_version"),
            is_forked_from_bundled=payload.get("is_forked_from_bundled", False),
            imported_from_package_id=payload.get("imported_from_package_id"),
            imported_from_recipe_id=payload.get("imported_from_recipe_id"),
            imported_at=payload.get("imported_at"),
            import_source_label=payload.get("import_source_label"),
            subtitle=payload.get("subtitle"),
            author=payload.get("author"),
            source_name=payload.get("source_name"),
            source_url=payload.get("source_url"),
            tags=payload.get("tags", []),
            category=payload.get("category"),
            difficulty=payload.get("difficulty"),
            servings=payload.get("servings"),
            prep_minutes=payload.get("prep_minutes"),
            cook_minutes=payload.get("cook_minutes"),
            total_minutes=payload.get("total_minutes"),
            notes=payload.get("notes"),
            cover_media_id=payload.get("cover_media_id"),
            display_settings=payload.get("display_settings", {}),
            deleted_at=payload.get("deleted_at"),
            step_links=[StepLink(**item) for item in payload.get("step_links", [])],
        )
