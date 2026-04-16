# Sync Protocol

## Scope and Shape

MVP sync is single-user LAN sync with desktop as source host.

- transport: HTTP JSON
- protocol versioned (`sync_protocol_version`)
- operation envelope with correlation IDs
- entity-level upsert + tombstone semantics

## Endpoints (Desktop Host)

- `GET /health`
- `GET /sync/status`
- `POST /sync/push` (mobile -> desktop changes)
- `POST /sync/pull` (mobile requests desktop changes since cursor)
- `POST /sync/probe` (diagnostic handshake and contract check)

## Envelope (All sync requests/responses)

- `sync_protocol_version`
- `request_id`
- `session_id`
- `device_id`
- `sent_at_utc`
- `payload`
- `errors[]`

## Change Model

Each changed entity includes:

- `entity_type`
- `entity_id`
- `op` (`upsert` | `delete`)
- `entity_version` (monotonic integer or timestamp sequence)
- `updated_at_utc`
- `body` (omitted for delete op)
- `source_scope` (`local` only in MVP push/pull flows)

Bundled content is not synced as mutable user data in MVP and is excluded from sync mutations.

Supported mutable local entity types in current baseline (desktop host apply + change fan-out):

- `recipe`
- `recipe_equipment_item`
- `recipe_ingredient_item`
- `recipe_step`
- `step_link`
- `step_timer`
- `global_equipment` (user equipment library; refinement phase)
- `catalog_ingredient` (user ingredient identity library; optional link from `recipe_ingredients`)
- `tag` (normalized tags; refinement phase)
- `collection`
- `collection_item`
- `meal_plan`
- `meal_plan_item`
- `grocery_list`
- `grocery_list_item`
- `recipe_user_state`
- `media_asset`

External sync remains JSON envelope based; internal host mapping targets normalized SQLite tables.

Recipe payloads continue to embed the full graph (`equipment`, `ingredients`, `steps`, `step_links`); child entity types allow incremental push/pull rows when clients send typed changes. Ingredient objects may include optional **sub-recipe** fields (`sub_recipe_id`, `sub_recipe_usage_type`, `sub_recipe_multiplier`, `sub_recipe_display_name`) carried in the same JSON shape as desktop `Recipe.to_dict()` / mobile `_recipeToSyncBody`.

## Conflict Strategy (MVP Default)

- Detect conflict when both sides changed same entity after last common sync version.
- Policy: **deterministic last-writer-wins by `updated_at_utc` + tie-break by `device_id`**, but never silently drop conflict metadata.
- Persist conflict record in sync log table and surface in diagnostics.
- For high-value fields in future versions, allow field-aware merge policies.

Conflict handling path is explicit in host behavior:

1. Detect stale update against local `updated_at_utc`.
2. Log conflict with correlation/request context.
3. Return per-entity status (`conflict`, `applied`, `rejected`) in response payload.
4. Never overwrite without recording conflict metadata.
5. Persist local/incoming `entity_version` alongside timestamps in `sync_conflicts`.

## Retry and Safety

- idempotency key = `request_id`
- retry safe for transient network failures
- partial failure returns per-entity result list
- failed entities remain queued locally for next sync

## Pull Behavior

- `POST /sync/pull` returns typed entity changes from normalized tables since `since_cursor`.
- Deletions are represented as tombstones (`op=delete`, `body=null`).
- Recipe graph rows may be returned as multiple entity changes, enabling future incremental client application.

Mobile client behavior in current phase:

- mobile sends versioned envelopes with `request_id`, `session_id`, and `device_id`
- mobile performs manual sync flow: **push** (queued local changes since `since_cursor`: recipe graph, meal plans, meal plan items, `media_asset`, `recipe_user_state`) then **pull**
- pulled `recipe` entities are persisted into the mobile SQLite graph through repository boundaries; additional pulled types handled in `sync_service.dart` include `collection`, `collection_item`, `meal_plan`, `meal_plan_item`, `grocery_list`, `grocery_list_item`, `recipe_user_state`, and `media_asset`
- child recipe rows (`recipe_equipment_item`, `recipe_ingredient_item`, `recipe_step`, `step_link`, `step_timer`) are applied when delivered inside a `recipe` payload or via the same graph upsert path—not as a separate “ignored” class in the mobile client
- sync status and errors are surfaced in UI and persisted in sync metadata storage

Link/timer sync notes:

- `recipe` payloads include `step_links` and `steps[].timers` definitions
- clients resolve links using stable IDs from `step_links.target_id`
- active timer runtime state is local-only and not included in sync payloads

## Timer Sync

MVP: sync timer definitions (`StepTimer`), not active running state.
Future: optional active timer snapshot sync using device-local authority token.

