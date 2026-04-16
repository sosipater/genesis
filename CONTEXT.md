# Recipe Forge Context

## What This App Is

Recipe Forge is a structured recipe platform, not a freeform notes app. A recipe is a graph of linked entities (recipe metadata, equipment, ingredients, steps, links, timers, media) that supports both creation and guided execution.

Desktop is optimized for authoring; mobile is optimized for cooking flow.

## Stack Decisions

- **Desktop**: Python 3.12+, PySide6, SQLite, FastAPI (local LAN sync host), Pydantic models.
- **Mobile**: Flutter (Dart), SQLite via `sqflite`, HTTP client for LAN sync.
- **Shared Contracts**: JSON Schema (versioned), JSON envelopes for sync and manifests.
- **Tooling**: Python scripts for schema validation, content validation, bundle export, sync probe.

## Non-Negotiable Architectural Boundaries

- Bundled content and local user content are stored and versioned separately.
- Timer state is persisted outside transient UI state.
- Sync DTOs are contract-driven and versioned; no implicit/destructive merges.
- Domain models are explicit typed structures, not shapeless dict blobs.
- UI modules do not own persistence rules or sync conflict policy.

## Content Scope Safety Rules

- `bundled_content/` is immutable app/package content at runtime.
- local database contains user-owned editable entities.
- "Global eligibility" in authoring means export candidacy only.
- app updates can add/update bundled recipes, never overwrite user local recipes.
- user forks from bundled recipes become separate local recipe IDs.

## Where To Look First

1. `docs/02_ARCHITECTURE.md`
2. `docs/03_DATA_MODEL.md`
3. `docs/04_SYNC_PROTOCOL.md`
4. `docs/07_CONTENT_PACKAGING.md`
5. `shared/schemas/*.schema.json`

## What Not To Break

- stable IDs for cross-entity linking
- schema versioning and migration paths
- separation of bundled/local content stores
- sync conflict visibility and no-silent-destructive writes
- mobile cooking flow section switching (Equipment / Ingredients / Steps)

## Current Phase

Search, collections, and working-set phase:

- deterministic search/filter flow added through service/repository layers
- persistent collections and membership model added without recipe duplication
- working set added as fast active-context grouping
- sync extended for collection entities, while working set remains intentionally device-local

Meal planning and grocery phase:

- meal plans and meal plan items added as synced local entities
- serving scaling and deterministic grocery aggregation implemented
- grocery lists added as generated snapshots with checklist state
- mobile now includes meal planning and grocery checklist workflow as primary weekly utility

Manual grocery editing + snapshot safety phase:

- grocery list rows now distinguish generated/manual and track user modifications
- users can manually add/edit/delete/reorder grocery items (mobile-first)
- regeneration is explicit and snapshot-based (new list), never silent overwrite of edited lists

Usage memory phase:

- `recipe_user_state` now persists favorites and opened/cooked counts/timestamps
- opened means recipe view opened; cooked means explicit user mark-cooked action
- favorites and recent views are surfaced on desktop/mobile without heavy analytics
- sync includes recipe user state while keeping tracking intentionally lightweight

Share import/export phase:

- share package format added for user-owned recipe portability and backup
- share import always creates local editable recipes; no silent overwrite of local data
- bundled content pipeline remains distinct from share package workflow
- import provenance is recorded on local recipes (`imported_from_package_id`, `imported_from_recipe_id`, `imported_at`)
- desktop is the file import/export endpoint in current increment; mobile consumes via sync/local store

Mobile authoring parity phase:

- mobile now supports full core recipe authoring (create/edit metadata, equipment, ingredients, steps, links, timers)
- mobile authoring uses dedicated controller/service boundaries to keep business logic out of widgets
- bundled recipes remain read-only in place on mobile and require duplicate-to-local before edits
- mobile persistence now includes full core metadata parity fields and timer `alert_sound_key`
- mobile sync now pushes local recipe graph edits so authored recipes propagate normally

Calendar-aware meal planning phase:

- meal plan items now support optional scheduling fields (`planned_date`, `meal_slot`, `slot_label`, `sort_order`)
- mobile planning now includes week-based grouped schedule visibility and fast schedule assignment
- grocery generation supports full plan, selected date range, and current-week slices while preserving deterministic aggregation
- desktop includes practical schedule management and grouped-by-date viewing without calendar-product overbuild
- external calendar integration is intentionally deferred in this phase for safety and scope control

Home surface phase:

- app now has a low-noise home entry model centered on Today / This Week / Quick Resume
- home logic is aggregated in dedicated service/controller layers, not computed ad hoc in widgets
- Today prioritizes actionable scheduled meals with direct open + mark-cooked paths
- This Week remains compact and supports quick orientation without replacing planner screens
- Quick Resume deterministically uses existing state (recent recipe, latest grocery, active plan, working set count)
- non-goals in this phase: AI recommendations, analytics dashboards, reminder systems

Media attachments phase:

- media attachments now use explicit owner-linked metadata (`media_assets`) and `*_media_id` references on recipe entities
- local file storage is app-managed; binary files are copied into managed media directories
- desktop supports practical cover/step attachment workflows; mobile supports staged path-based cover/step attachment
- mobile/desktop viewers show media when available and provide explicit fallback when files are missing
- sync currently transfers media metadata only; binary media transfer is deferred
- share/export currently rejects media-bearing recipes/packages explicitly to avoid silent attachment loss

Undoability baseline:

- meal plan deletion now supports explicit undo on mobile and desktop

Notifications and reminders phase:

- added a lightweight, opt-in notification model focused on meal reminders and timer completion
- reminder intent now lives on synced meal-plan-item schedule fields; actual scheduling/execution is device-local
- mobile schedules/cancels local notifications when meal items are created/edited/deleted
- timer runtime now emits completion events that trigger local notifications when globally enabled
- user control is explicit: global notification toggle + reminder defaults + per-meal reminder flags
- desktop notification UX remains intentionally minimal/deferred in this increment

Release hardening phase:

- desktop runtime storage now uses explicit app-data directories (db/media/logs/backups/temp/preferences)
- backup/restore operational workflow added with manifest + checksum validation and explicit replace semantics
- diagnostics tooling now reports app/schema/protocol/share-format versions, paths, data counts, and media health
- media hardening includes type/size validation plus orphan/missing/dangling scan with explicit cleanup action
- desktop startup/restore errors now surface clearer local operational guidance (e.g., locked DB on restore)

Release readiness report increment:

- added `tools/release_readiness_report.py` as a single non-destructive pre-release confidence command
- report covers versioning, data health, media health, path readiness, optional backup validation, and optional desktop test execution
- output is terminal-readable with explicit `PASS`/`WARN`/`FAIL` states and actionable summary
- desktop wrapper exposes this via `desktop.ps1 release-check`

First-use UX increment:

- mobile Home, Library, Plan, and Grocery empty states point to one or two actions (create, plan, sync) without long copy
- recipe metadata: title and notes first; other fields grouped as optional on mobile and desktop
- ingredients: quick free-text line is default; structured fields are secondary
- step links, timers, and images: optional, collapsible presentation; list rows avoid emphasizing empty timer or link counts
- planning: dinner default and collapsed slot or reminder options; quick Today on schedule dialogs where relevant
- share or export: user-visible explanation when media would be left behind; diagnostics, About, and Sync mention backups lightly

Authoring refinement phase (equipment reuse, tags, clearer steps/timers):

- **Global equipment**: users maintain a reusable pool (`global_equipment`); recipe equipment rows may optionally set `global_equipment_id`. Names on recipe rows are snapshots; updating the global record affects future picks, not existing recipe rows automatically.
- **Tags**: normalized `tags` + `recipe_tags` join; recipe `tags` JSON stays the portable list on the recipe payload; desktop metadata + library support tag picking and multi-tag filtering (match all).
- **Step authoring**: collapsible **Advanced (optional)** on the Steps tab holds links, timers, and step image attach/remove; new steps open Advanced once to reduce “create then reopen” friction.
- **Link UI copy**: user-facing **Reference name** / **Display text (optional)** replace “token key” / “label override” in the desktop dialog; internals remain ID- and token-based.
- **Timer UI**: preset **Sound** dropdown + **Vibrate** map to `alert_sound_key` and `alert_vibrate`; no raw key entry.
- **Sync**: push/pull allowlist includes `global_equipment` and `tag` entity types; migration v11 is additive.
- **Mobile**: parity for these fields is expected to follow in the mobile schema/repository/editor layers (Flutter `schemaVersion` / migrations not yet fully merged in this increment).

## Source control and handoff

- **Canonical remote**: [github.com/sosipater/genesis](https://github.com/sosipater/genesis) — empty-repo first push should use `main` as the default branch.
- **Desktop DB schema**: SQLite migrations top out at **v11** (global equipment, tags/`recipe_tags`, `recipe_equipment.global_equipment_id`, `step_timers.alert_vibrate`). Mobile may lag; see refinement bullets above.
- **Docs to read for a cold start**: `README.md` (map + commands), this file, then `docs/02_ARCHITECTURE.md`, `docs/03_DATA_MODEL.md`, `docs/04_SYNC_PROTOCOL.md`, `docs/05_UI_UX_GUIDELINES.md`, `docs/09_ROADMAP.md`.
