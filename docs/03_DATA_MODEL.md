# Data Model

## Modeling Strategy

- Use stable UUIDs for all major entities.
- Keep explicit tables/models per entity class.
- Preserve both human-friendly raw fields and structured fields where needed.
- Support soft deletion (`deleted_at`) for sync-safe tombstones.
- Persist editable recipe graph in local tables only for `scope=local`.
- Treat bundled recipes as read-only files loaded through manifest, not imported into local user tables.
- Use normalized relational tables for local data; no `payload_json` source of truth remains.

## Local SQLite Tables (Normalized)

- `recipes`: local recipe metadata and top-level fields (`entity_version`, timestamps, soft delete).
- `recipe_equipment`: equipment items linked by `recipe_id`.
- `global_equipment`: user-owned reusable equipment library (name, optional notes/media); synced like other user entities.
- `tags`: normalized tag definitions (`name`, optional `color`).
- `recipe_tags`: join table (`recipe_id`, `tag_id`) kept in sync with recipe tag assignments.
- `recipe_ingredients`: ingredient items linked by `recipe_id`, preserving `raw_text` + structured fields.
- `recipe_steps`: ordered execution steps linked by `recipe_id`.
- `step_links`: link anchors for step references linked by `step_id`.
- `step_timers`: timer definitions linked by `step_id`.
- `media_assets`: local media metadata references.
- `sync_state`: per-entity sync bookkeeping.
- `sync_conflicts`: explicit conflict records with local/incoming timestamp and version values.

All child tables include:

- stable `id`
- `entity_version`
- `created_at`, `updated_at`, `deleted_at`
- explicit `display_order` where ordering is user-visible
- foreign key constraints for relationship integrity

## Core Entities

## `Recipe`

- `id`
- `scope` (`bundled` | `local`)
- `bundled_content_version` nullable
- `bundle_export_eligible` (local export selection)
- `export_bundle_recipe_id` nullable
- `export_bundle_recipe_version` default 1
- `origin_bundled_recipe_id` nullable
- `origin_bundled_recipe_version` nullable
- `is_forked_from_bundled` boolean
- `imported_from_package_id` nullable (share package lineage)
- `imported_from_recipe_id` nullable (source recipe ID from share package)
- `imported_at` nullable
- `import_source_label` nullable
- `title`, `subtitle`, `author`
- `source_name`, `source_url`
- `notes`, `difficulty`, `servings`
- `prep_minutes`, `cook_minutes`, `total_minutes`
- `category`, `status` (`draft` | `published` | `archived`)
- `cover_media_id` nullable
- `display_settings_json` nullable
- `created_at`, `updated_at`, `deleted_at` nullable

## `RecipeEquipmentItem`

- `id`, `recipe_id`
- `name`, `description`, `why_used`
- `is_required`
- `notes`, `affiliate_url`, `alternate_equipment_text`
- `media_id` nullable
- `display_order`
- `global_equipment_id` nullable — optional link to a row in `global_equipment` when this line was picked from the shared pool; recipe rows still store their own `name` and details as a snapshot for that recipe.

**Global equipment behavior**

- Editing a `global_equipment` row (name, notes, media) updates the library record for future picks; existing `recipe_equipment` rows are not rewritten automatically, so past recipes keep the text they had when saved.
- Recipe lines can omit `global_equipment_id` for fully custom one-off equipment.

## `GlobalEquipment` (library)

- `id`, `name`, `notes` nullable, `media_id` nullable
- `entity_version`, `created_at`, `updated_at`, `deleted_at` nullable
- Sync entity type: `global_equipment`

## Tags (normalized)

- `tags`: `id`, `name` (case-insensitive unique), optional `color`, versioning + soft delete
- `recipe_tags`: associates recipes with tag IDs; maintained when recipes are saved from the recipe’s tag list (`recipes.tags_json` remains the portable JSON projection on the recipe row)
- Sync entity type: `tag`

## `RecipeIngredientItem`

- `id`, `recipe_id`
- `raw_text`
- `quantity_value` nullable
- `quantity_text` nullable
- `unit` nullable
- `ingredient_name` nullable
- `preparation_notes`, `substitutions`, `affiliate_url` nullable
- `recommended_product` nullable
- `media_id` nullable
- `is_optional`
- `display_order`

## `RecipeStep`

- `id`, `recipe_id`
- `title` nullable
- `body_text`
- `step_type` (`instruction` | `note` | `section_break`)
- `estimated_seconds` nullable
- `media_id` nullable
- `display_order`

## `StepLink`

- `id`, `step_id`
- `target_type` (`ingredient` | `equipment`)
- `target_id`
- `token_key` (stable inline anchor token)
- `label_snapshot` (render fallback text)
- `label_override` nullable

Storage and resolution contract:

- Step text stores token markers such as `[[ingredient:spaghetti]]`.
- `step_links` stores stable target IDs (`target_type`, `target_id`) plus token metadata.
- Rendering resolves by ID first, then falls back to `label_snapshot` if target is missing.
- Label overrides are display-only and do not affect target identity.
- No runtime UI link lookup uses ingredient/equipment name matching.

Desktop authoring contract:

- Link authoring always selects a target entity from current recipe lists (ingredient/equipment).
- Authoring writes both:
  - structured `step_links` record with stable IDs
  - controlled token marker in `recipe_steps.body_text` (`[[target_type:token_key]]`)
- Token updates/removals are performed by authoring service methods to avoid drift between body text and link records.
- Preview resolves using `step_links` first and falls back safely to snapshot labels when targets are missing.

Mobile authoring contract:

- Mobile authoring uses the same `step_links` storage semantics as desktop (`target_type`, `target_id`, `token_key`).
- Link add/edit/remove on mobile is performed through authoring service logic that keeps body token markers synchronized.
- Link identity remains stable ID-based and never depends on display labels.

## `StepTimer`

- `id`, `step_id`
- `label`
- `duration_seconds`
- `auto_start`
- `alert_sound_key` nullable (internal preset key; UI maps friendly labels to these values)
- `alert_vibrate` boolean — whether the device should vibrate on timer completion when supported

Timer scope in this phase:

- Timer definitions are persisted and synced.
- Mobile runtime executes timers locally in an in-memory controller with start/pause/resume/cancel.
- Active runtime state is visible globally in-app and survives in-app navigation.
- Active runtime state is intentionally not background-executed and not synced cross-device yet.

Desktop timer authoring:

- Timer definitions are authored as explicit per-step `StepTimer` records (label, duration, auto_start, alert_sound_key, alert_vibrate).
- Desktop preview in this phase is static/structural; full desktop runtime execution remains secondary to mobile-first execution.

Mobile timer authoring:

- Mobile can add/edit/remove structured `StepTimer` entities per step.
- Timer definitions remain separate from step text and sync as recipe graph data.
- `alert_sound_key` is persisted in mobile schema and mapping.

## `MediaAsset`

- `id`
- `owner_type`, `owner_id`
- `file_name`
- `relative_path`
- `local_path` nullable (derived compatibility field)
- `bundled_path` nullable
- `mime_type`
- `width`, `height` nullable
- `checksum_sha256` nullable

Ownership mapping in this phase:

- recipe cover: `owner_type=recipe_cover`, `owner_id=recipe.id`, referenced by `recipes.cover_media_id`
- step image: `owner_type=step`, `owner_id=recipe_steps.id`, referenced by `recipe_steps.media_id`
- ingredient image: `owner_type=ingredient`, `owner_id=recipe_ingredients.id`, referenced by `recipe_ingredients.media_id`
- equipment image: `owner_type=equipment`, `owner_id=recipe_equipment.id`, referenced by `recipe_equipment.media_id`

Storage strategy:

- file binaries live in app-managed local media directories
- DB stores metadata + relative paths only
- missing files are treated as fallback state (metadata can exist while file is absent on a device)

## `Tag` and Mapping

- `Tag(id, name, normalized_name)`
- `RecipeTag(recipe_id, tag_id)`

## `SyncState`

- `entity_type`, `entity_id`
- `entity_updated_at`
- `last_modified_device_id`
- `last_synced_at`
- `sync_version`
- `is_tombstone`

## `Collection`

- `id`
- `name`
- `created_at`, `updated_at`, `deleted_at`
- `entity_version`

## `CollectionItem`

- `id`
- `collection_id`
- `recipe_id`
- `created_at`, `updated_at`, `deleted_at`
- `entity_version`
- uniqueness constraint on (`collection_id`, `recipe_id`)

## `WorkingSetItem`

- `id`
- `recipe_id` (single active membership per recipe)
- `created_at`, `deleted_at`

Working set is intentionally independent from collections and optimized for rapid add/remove actions.

## `RecipeUserState`

Lightweight local-first memory of personal usage and preference.

- `recipe_id` (PK)
- `is_favorite` boolean
- `last_opened_at` nullable
- `last_cooked_at` nullable
- `open_count` integer
- `cook_count` integer
- `pinned` boolean (reserved)
- `created_at`, `updated_at`, `deleted_at`
- `entity_version`

Definitions:

- opened: recipe view opened by user
- cooked: explicit user action to mark cooked
- favorite: persistent user preference toggle
- recent: derived from timestamps, never hand-maintained list

## `MealPlan`

- `id`
- `name`
- `start_date` nullable
- `end_date` nullable
- `notes` nullable
- `created_at`, `updated_at`, `deleted_at`
- `entity_version`

## `MealPlanItem`

- `id`
- `meal_plan_id`
- `recipe_id`
- `servings_override` nullable
- `notes` nullable
- `planned_date` nullable (`YYYY-MM-DD`)
- `meal_slot` nullable (`breakfast` | `lunch` | `dinner` | `snack` | `custom`)
- `slot_label` nullable (used when `meal_slot=custom`)
- `sort_order` integer (ordering within date/slot)
- `reminder_enabled` boolean (explicit per-item opt-in)
- `pre_reminder_minutes` nullable integer (e.g. 15/30)
- `start_cooking_prompt` boolean (optional lightweight nudge)
- `created_at`, `updated_at`, `deleted_at`
- `entity_version`

Meal plans reference recipe IDs only and never duplicate recipe payloads.

Scheduling semantics:

- unassigned item: `planned_date` is null; item remains in plan backlog and is excluded from date-range grocery generation.
- date-assigned item: `planned_date` is set; item participates in week/range grouping and filtered grocery snapshots.
- meal slot: optional structure for day ordering and meal context; custom labels are stored separately in `slot_label`.
- week view grouping: grouped by `planned_date`, then ordered by slot and `sort_order`.
- grocery source set:
  - full plan snapshot uses all meal-plan items (assigned + unassigned)
  - range/week snapshot uses only items with `planned_date` in the selected interval

Reminder semantics:

- reminder fields are part of synced meal-plan-item schedule intent.
- actual scheduled notifications are computed/scheduled per device locally.
- no recurrence engine is introduced in this phase.

## `ReminderNotification` (Device-Local)

- `id`
- `type` (`meal_reminder` | `meal_pre_reminder` | `start_cooking_prompt` | `timer_complete`)
- `reference_type` (`meal_plan_item` | `timer`)
- `reference_id`
- `scheduled_time_utc`
- `payload_json` (navigation context such as `recipe_id`, `step_id`)
- `enabled`
- `updated_at`, `deleted_at`

This table is local operational state and is intentionally not synced.

## `GroceryList`

- `id`
- `meal_plan_id` nullable (snapshot origin)
- `name`
- `generated_at`
- `created_at`, `updated_at`, `deleted_at`
- `entity_version`

## `GroceryListItem`

- `id`
- `grocery_list_id`
- `name`
- `quantity_value` nullable
- `unit` nullable
- `checked` boolean
- `source_recipe_ids_json` for traceability
- `source_type` (`generated` | `manual`)
- `generated_group_key` nullable (stable aggregation signature for generated rows)
- `was_user_modified` boolean
- `sort_order` integer
- `created_at`, `updated_at`, `deleted_at`
- `entity_version`

Grocery list is a generated snapshot; it is not tightly coupled to later meal-plan edits.

Manual editing semantics:

- Manual rows are created with `source_type=manual`.
- Generated rows retain `source_type=generated`.
- Any user edit/toggle on an existing row sets `was_user_modified=true`.
- Row ordering is explicit via `sort_order` and synced as data.

Regeneration safety model:

- Regeneration is explicit and creates a **new grocery snapshot/list**.
- Existing grocery lists are never silently overwritten.
- Manual-only rows and user-modified generated rows remain in prior snapshots unless explicitly deleted by user.

Reconciliation rule set (current phase):

- No in-place merge is performed yet.
- New snapshot is computed deterministically from current meal plan output.
- Prior snapshot remains available as working artifact/history.

## Usage State Sync Decision

- `recipe_user_state` syncs across devices (favorites + opened/cooked state/counts).
- Conflict handling remains timestamp/version aware via existing sync conflict path.
- Tracking remains intentionally lightweight (no granular interaction event log).

## Share Import Provenance

Share import is distinct from bundled provenance:

- share import always creates a new local editable recipe ID
- original share recipe ID is retained in `imported_from_recipe_id`
- share package lineage is retained in `imported_from_package_id`
- bundled provenance fields are cleared for imported recipes unless explicitly set by later workflows

This preserves portability lineage without implying bundled ownership.

## Migration Note

Migration v2 converts legacy `local_recipes.payload_json` rows into normalized tables and removes the legacy table to prevent competing sources of truth.

Migration v3 adds provenance and export metadata columns on local recipes to support bundled packaging workflows and safe fork tracking.

Migration v4 adds `collections`, `collection_items`, and `working_set_items`, with sync-ready version tracking on collections and collection memberships.

Migration v5 adds meal-planning and grocery snapshot tables (`meal_plans`, `meal_plan_items`, `grocery_lists`, `grocery_list_items`).

## Scaling and Grocery Rules

- Scale factor per meal plan item is `servings_override / recipe.servings` when both are present and positive.
- Structured ingredient quantities (`quantity_value`) are scaled numerically.
- Raw-text-only ingredients remain unchanged.
- Grocery grouping key is deterministic:
  - normalized `ingredient_name` when present, else normalized `raw_text`
  - plus normalized `unit`
- Quantities are combined only when grouping key matches exactly; different units remain separate items.

## Structured Diff Model

Recipe diffing uses stable IDs and normalized entity groups:

- recipe metadata fields
- equipment
- ingredients
- steps
- step links
- step timers

For each entity group, diff output includes deterministic:

- `added`
- `removed`
- `modified` (field-level `before`/`after`)
- `order_changed` and `order_changes` where ordering is meaningful

Entity matching is ID-based only; names are never used as identity keys.

