# Architecture

## High-Level System

Genesis is a dual-app monorepo with shared contracts. The public Git remote for this codebase is [github.com/sosipater/genesis](https://github.com/sosipater/genesis).

- **Desktop app**: Authoring UI + local SQLite + local HTTP sync host + export tooling.
- **Mobile app**: Cooking UI + local SQLite + LAN sync client.
- **Shared layer**: Versioned JSON schemas and contract samples.

## Module Boundaries

### Desktop

- `ui`: PySide6 views/view-models (authoring workflow)
- `domain`: typed domain entities + business rules
- `persistence`: normalized SQLite schema + migrations + repositories (desktop schema migrations include **v13**: optional sub-recipe columns on `recipe_ingredients`; **v12** `catalog_ingredient` + optional `catalog_ingredient_id`; **v11** global equipment pool, tags + `recipe_tags`, optional `global_equipment_id` on recipe equipment, `alert_vibrate` on step timers)
- `services`: editor orchestration between UI and repository/bundled loader
- `viewmodels`: explicit editor state (dirty/read-only/save eligibility)
- `bundled_loader`: read-only bundled manifest/recipe readers (separate from repositories)
- `services/bundle_export_service.py`: deterministic local->bundled export pipeline and manifest generation
- `services/recipe_diff_service.py`: deterministic structured diff model used by tooling/export warnings/UI compare
- `services/media_service.py`: managed local media import/copy/remove and ownership-safe metadata writes
- `sync_host`: HTTP API, diff logic, conflict handling
- `packaging`: bundled export and manifest generation
- `timers`: timer state engine + persistence adapter
- `diagnostics`: logging, health, sync history readers
- `config`: schema-validated configuration loader and accessor

### Mobile

- `app`: bootstrap, dependency graph, and navigation shell
- `config`: protocol and host defaults
- `data/db`: SQLite schema for local recipe graph persistence
- `data/models`: typed mobile recipe/sync models
- `data/repositories`: recipe and sync metadata persistence boundaries
- `data/sync`: typed LAN sync API client + sync service
- `features/library`: local recipe list and open/create/edit entry flow
- `features/recipe_view`: cooking-focused tabbed recipe view (Equipment/Ingredients/Steps)
- `features/recipe_editor`: mobile authoring controller + service + compact section editors
- `features/media`: mobile managed media import/remove helper
- `features/sync`: host configuration + test connection + manual sync

## Data Ownership

- Domain entities own invariants.
- Repositories own persistence mapping and aggregate assembly from normalized tables.
- Services coordinate domain/repository operations for UI workflows (create/save/duplicate).
- Sync DTOs are separate from DB rows and UI models.
- Content package manifest is externalized from local user DB.
- Bundled recipes are read-only overlay data and are never auto-imported into local editable tables.
- Local recipes may carry provenance metadata (`origin_bundled_*`, export bundle IDs/versions) without changing local ownership.

Mobile bundled/local behavior in this phase:

- mobile does not ship bundled assets yet; bundled data can still be represented by `scope` when synced
- local mobile DB stores synced recipe graph and keeps scope distinctions visible in UI
- **schema v13** on mobile aligns with desktop for **sub-recipe** columns on `recipe_ingredients`, plus **v12** **catalog ingredient** library + link column, **v11** reusable **global equipment**, normalized **tags**, recipe equipment `global_equipment_id`, and timer `alert_vibrate`
- architecture keeps room for future read-only bundled asset overlay on device
- chosen strategy remains sync/local graph on mobile for now (no shipped bundled assets in mobile package yet)

Mobile authoring parity contract:

- mobile uses the same normalized recipe graph (`recipes`, equipment, ingredients, steps, links, timers)
- mobile authoring logic is centralized in controller/service modules, not widgets
- bundled recipes remain read-only in place; editing requires duplicate/fork into local scope
- mobile save path writes full recipe graph transactions via repository boundaries
- sync push now includes local recipe graph changes authored on mobile

Media architecture contract (current increment):

- media files are stored in app-managed local media directories (not embedded in recipe rows)
- `media_assets` holds metadata + ownership + relative path
- recipes and child entities reference media by stable `*_media_id` fields
- missing files are handled as non-fatal view fallbacks
- sync currently transfers media metadata only; file transfer is intentionally deferred

## Desktop Authoring UI Structure

- `ui/windows/main_window.py`: shell composition and high-level event orchestration.
- `ui/panels/library_panel.py`: recipe navigation and creation/duplication entry points.
- `ui/panels/metadata_panel.py`: metadata form editing.
- `ui/panels/equipment_panel.py`, `ingredients_panel.py`, `steps_panel.py`: section-specific editors with ordering controls.
- `ui/widgets/list_editor_widget.py`: shared table/reorder control widget.

UI widgets do not access SQL directly; all persistence operations route through `EditorService` and `RecipeRepository`.

## Tradeoff Decisions

- **SQLite over document DB**: fast local relational joins for linked entities and order-heavy lists.
- **Tokenized step references**: maintain renderable inline references while keeping stable IDs in a separate link table.
- **Desktop-hosted LAN sync for MVP**: operationally simple and inspectable before cloud complexity.
- **Recipe-level write transaction with entity-level sync surface**: local writes apply a full recipe graph atomically, while sync emits and accepts typed entity changes (`recipe`, `recipe_step`, etc.) for future incremental sync.

## Configuration

Config is schema-versioned and loaded from `shared/contracts` defaults + app overrides:

- feature toggles
- sync settings
- logging levels/paths
- UI section labels
- bundled content paths

Current baseline uses `shared/schemas/app_config.schema.json` to validate `shared/contracts/app_config.default.json` before startup.

## Search, Collections, and Working Set

- Search is centralized outside widgets:
  - Desktop uses `RecipeSearchService` for deterministic scoring and filter composition.
  - Mobile uses repository search APIs; widgets only supply query/filter state.
- Search coverage includes recipe metadata and execution graph text (ingredients/equipment/steps).
- Collections are persistent local entities with many-to-many recipe references (`collections`, `collection_items`), never embedded inside recipe payloads.
- Working set is a separate quick-context store (`working_set_items`) optimized for high-frequency add/remove.
- Sync decision:
  - collections + collection membership sync as explicit local entity types.
  - working set remains device-local by design to preserve per-device active context.

## Release Hardening Operational Boundaries

Current operational trust layer introduces dedicated service/tool boundaries:

- `runtime_paths`: canonical app-data directory resolution for desktop runtime state.
- `services/backup_service.py`: backup package create/validate/restore logic.
- `services/diagnostics_service.py`: version/path/data/media health reporting.
- `services/media_service.py`: media validation + scan + explicit cleanup operations.
- `tools/ops_desktop.py`: command-line operational entrypoint (backup/restore/diagnostics/media-scan).

Safety constraints:

- backup/restore is explicit and non-implicit; restore uses replace semantics only in this phase.
- media cleanup is report-first; destructive cleanup requires explicit operator action.
- operational logic remains outside UI widgets and routes through services/tools.

