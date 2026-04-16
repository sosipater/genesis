# Roadmap

## How to read this document

- **Dependency order matters**: prefer work that **unlocks later features** and **avoids rework** (stable IDs, migrations, sync entity registration, mobile/desktop parity).
- **Idea bank**: exploratory and future directions live in `docs/10_IDEA_BACKLOG.md` so they are not lost; not every item is scheduled here.
- **Naming**: the repo/product is **Genesis** in code; **Recipe Forge** appears in some product language — same system.
- **Long-term horizon**: recipes stay the primary concept; architecture should remain compatible with broader **procedural knowledge** later **without** renaming core types prematurely (`10_IDEA_BACKLOG.md`).

## Current platform state (high level)

**Stable today**

- Dual app: **desktop** (Python, PySide6, SQLite, LAN sync host) and **mobile** (Flutter, SQLite, sync client).
- **Recipe graph**: metadata, equipment, ingredients, steps, links, timers, media metadata, scoped bundled vs local.
- **Meal planning, scheduling, grocery** snapshots with manual edit safety and regeneration semantics.
- **Search, collections, working set**, favorites / recent / cooked memory, home surfaces.
- **Sync**: versioned protocol, entity-level push/pull, conflict logging, many entity types on wire.
- **Share packages** (desktop file path), **backup/restore**, **diagnostics**, **release readiness** tooling.
- **Desktop DB** schema **v13**: adds **sub-recipe columns** on `recipe_ingredients` (plus **v12** catalog ingredient link, **v11** global equipment, tags, vibrate, etc.).

**Gaps / alignment in flight**

- (none listed here — next tranche picks up from backlog / polish.)

## Near-term roadmap (dependency-ordered)

1. **Mobile v11 parity (reusable equipment + tags + vibrate)** — **implemented in tree**  
   Align SQLite + repository + sync apply/push + authoring UX with desktop refinement phase. *Unlocks consistent sync and establishes patterns for catalog entities.* Verify on-device against desktop host after upgrading an existing mobile DB.

2. **Ingredient catalog (groundwork)** — **in progress / shipped in tree**  
   Optional `catalog_ingredient` with `name` + normalized matching + optional `notes`; nullable `recipe_ingredients.catalog_ingredient_id`; sync entity `catalog_ingredient`; desktop + mobile lightweight pick/suggest/save UX — **no** nutrition, units overhaul, or forced catalog usage. *Builds on v11 reuse patterns.*

3. **Organization polish**  
   **Search + tag filtering stretch (in tree):** library search uses the **ingredient catalog** (linked names) plus raw lines, tags, and graph text; tag **match-all** filters on desktop and mobile; optional **ingredient-focused** filter; subtle match hints in results. **Still no** deep folders, recommendations, or heavy search UI.

## Mid-term roadmap

- **Sub-recipe / composable recipes** — **first slice shipped in tree**: explicit `full_batch` / `fraction_of_batch` (+ multiplier), recursive grocery expansion with cycle + depth guards, share closure + atomic import validation, desktop + mobile authoring and recipe-view navigation. **Deferred**: arbitrary unit conversion, “N cups of sub-recipe” density math, graph visualization, cross-package share references without bundling.
- **Share format extensions** for equipment/catalog slices where portable knowledge requires it.
- **Theme/settings** consolidation and optional color themes (non-semantically-loaded colors only).

## Long-term / conceptual

- **Procedural knowledge** beyond recipes on the same technical base (schemas, sync, packages).
- **Media at scale** (video, high-res): documented strategy for optional online/streaming; local-first remains default.
- **Excel / bulk tooling** as a **power-user layer**, not a replacement for core authoring UX.

## Historical delivery log (phases 0–6)

The sections below record **what shipped** in earlier phase numbering. They are retained for continuity.

## Phase 0 - Foundation (completed)

- finalize architecture docs and boundaries
- create monorepo scaffold
- define versioned shared schemas
- build validation and packaging utility scripts

## Phase 1 - Desktop Core

- implement domain models and SQLite migrations
- implement recipe editor data operations
- implement local sync host skeleton (`/health`, `/sync/status`, pull/push stubs)
- add structured logging and diagnostics panel scaffolding

Phase 1 status:

- completed normalized persistence and entity-aware sync baseline
- completed first desktop authoring shell with library, metadata editing, section editors, dirty tracking, and bundled duplication flow

## Phase 2 - Mobile Core

- create Flutter app shell and navigation
- local persistence schema aligned with shared contracts
- implement LAN connectivity configuration and sync client
- build recipe screen with section tabs and step execution view

Phase 2 status:

- completed Flutter shell with Library + Sync destinations
- completed local SQLite baseline for recipe graph entities
- completed typed LAN sync client and manual sync flow
- completed cooking-oriented recipe view with Equipment/Ingredients/Steps tab switching

## Phase 3 - Sync Robustness

- full bidirectional sync for recipe graph entities
- conflict detection + diagnostics surfacing
- retry queue and partial failure handling
- integration tests across desktop/mobile fixtures

## Phase 4 - Authoring & Cooking UX Depth

- desktop drag reorder + link insertion workflows
- mobile timer bar/chips and quick overlay details
- improved metadata editing and validation UX

Phase 4 status (current increment):

- first-use UX pass: clearer empty states, lighter recipe metadata/ingredient defaults, softer presentation of links/timers, faster meal-plan scheduling defaults (dinner-first), explicit share/media messaging, and light backup trust copy (no onboarding wizard)
- mobile step flow is now interactive with tappable ingredient/equipment references
- mobile link detail sheets and missing-link fallback behavior implemented
- mobile local timer runtime controller implemented with start/pause/resume/cancel
- active timers visible persistently across app navigation
- desktop has lightweight clickable step-link detail popup support

Authoring follow-through status:

- desktop now supports structured step link authoring (add/edit/remove) against recipe entity IDs
- desktop now supports structured step timer authoring (add/edit/remove with validation)
- desktop selected-step preview now reflects interactive link behavior during authoring

Refinement phase (reuse + organization, desktop-first):

- global reusable **equipment library** (`global_equipment`) with optional links from recipe equipment rows
- normalized **tags** + `recipe_tags` join; library filtering by tags (match all)
- friendlier **link** and **timer** authoring copy and controls (presets + vibrate)
- collapsible **advanced** block on steps for links/timers/images at creation time
- schema migration v11 (additive); sync extended for `global_equipment` and `tag` entities

## Phase 5 - Content Packaging Pipeline

- export eligible local recipes into bundle package
- checksum + manifest generation
- bundle validation automation for release process

Phase 5 status:

- desktop metadata supports bundled export eligibility flags
- desktop action exports eligible local recipes into bundled package files + manifest
- local recipes receive/export stable bundled IDs and bundled version metadata
- local fork provenance metadata retained when duplicating bundled recipes
- validator enforces manifest integrity, duplicate ID safety, and bundled link target integrity
- deterministic diff tooling added for bundled version diffs and local-vs-origin comparison

## Phase 6 - Expansion

- search/tag filtering/favorites/collections
- shopping list generation
- richer media workflows and step-level media
- import/export and print/share capabilities

Phase 6 status (current increment):

- deterministic search/filter service layer added on desktop and mobile repository path
- persistent collections and collection membership implemented
- quick working set behavior implemented as distinct active-context model
- sync extended for `collection` and `collection_item`; working set intentionally remains device-local

Phase 6 status (meal planning increment):

- meal plan model implemented (`meal_plans`, `meal_plan_items`)
- deterministic serving scaling and grocery aggregation pipeline implemented
- grocery snapshot model implemented (`grocery_lists`, `grocery_list_items`) with checklist state
- mobile meal planning + grocery checklist flow added as primary weekly workflow
- sync extended for meal plans and grocery snapshots

Phase 6 status (manual grocery editing increment):

- grocery rows now track generated/manual/user-modified metadata
- mobile grocery workflow supports manual add/edit/delete/reorder
- explicit regenerate action now creates a new snapshot to avoid silent data loss
- sort order and manual edits are persisted and synced

Phase 6 status (usage memory increment):

- added `recipe_user_state` model for favorites + opened/cooked timestamps/counts
- desktop and mobile now track open events and explicit cooked actions
- favorites and recents are surfaced through lightweight views/filters
- sync extended for `recipe_user_state` to keep personal state coherent across devices

Phase 6 status (share import/export increment):

- desktop share package export/import implemented for local user recipes
- safe import collision strategy implemented (new local IDs, no overwrite, repeated-import skip)
- import provenance metadata added on local recipes for package lineage
- share package tooling added (`tools/export_recipe_share.py`, `tools/import_recipe_share.py`)
- mobile strategy remains desktop-first for file import/export in this increment

Phase 6 status (mobile authoring parity increment):

- mobile now supports real recipe create/edit/save flows for local recipes
- mobile section editors now support add/edit/delete/reorder for equipment, ingredients, and steps
- mobile step editor now supports structured link and timer authoring (not view-only)
- bundled recipes remain read-only on mobile and require duplicate-to-local before editing
- mobile sync now pushes local recipe graph edits in addition to user-state updates

Phase 6 status (calendar-aware meal planning increment):

- meal-plan items now support optional schedule metadata (`planned_date`, `meal_slot`, `slot_label`, `sort_order`)
- mobile planner now provides week-aware grouped scheduling with fast date/slot assignment
- grocery generation now supports full-plan, week-slice, and explicit date-range snapshots
- desktop now supports schedule assignment and grouped schedule review for operational management
- external calendar integration intentionally deferred; internal schedule model remains primary

Phase 6 status (home surface increment):

- mobile now includes a compact Home tab focused on Today / This Week / Quick Resume
- Today section is actionable (open recipe, mark cooked, route to planner when empty)
- This Week section provides compact grouped visibility without replacing planner workflows
- Quick Resume deterministically surfaces most recent recipe, latest grocery snapshot, active plan, and working-set signal
- desktop now includes lightweight Home overview access for planned/recent quick context
- no recommendation engine or analytics dashboard added in this increment

Phase 6 status (media attachments increment):

- managed local media metadata model activated (`media_assets` + explicit ownership mappings)
- recipe cover and step media attach/remove workflows added to desktop and staged mobile authoring
- mobile viewing now shows cover/step images with graceful missing-file fallback
- sync includes media metadata entities while media binary transfer is intentionally deferred
- share/export now explicitly rejects media-attached recipes/packages in this phase to avoid silent data loss
- meal plan deletion now supports undo flows on mobile and desktop

Phase 6 status (notifications/reminders increment):

- mobile now includes a lightweight notification layer for meal reminders and timer completion
- meal reminder intent is modeled on `meal_plan_items` (per-item enable + optional pre-reminder/start prompt)
- runtime scheduled notification records are device-local and managed in dedicated service/repository boundaries
- schedule edits/deletes now reschedule/cancel reminders to prevent stale notifications
- global notification enablement and reminder defaults are user-controlled and explicit
- desktop full notification UX remains intentionally deferred (mobile-first)

Phase 6 status (release hardening increment):

- explicit desktop runtime path strategy added (`db`, `media`, `logs`, `backups`, `temp`, preferences)
- desktop operational backup package implemented with manifest/checksum validation and explicit replace restore
- media hardening added: file type + file size validation, orphan/missing/dangling scan, explicit orphan cleanup
- diagnostics tooling added for version/schema/protocol/path/health summaries (`tools/ops_desktop.py`)
- desktop UI now exposes About/version and operational actions (backup/restore/media health/diagnostics)
- mobile sync screen now exposes app/schema/protocol/share-format versions

