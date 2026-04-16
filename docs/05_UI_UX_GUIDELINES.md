# UI/UX Guidelines

## Global Principles

- dark-mode-first
- quick section switching
- low cognitive load while cooking
- strong editing ergonomics on desktop
- calm, low-noise home entry focused on immediate next actions

## Desktop UX Structure

Primary layout:

- left: library/search/tags/filters
- center: recipe editor workspace
- right: inspector/properties/preview

Recipe editor section navigation is persistent and one-click:

- Equipment
- Ingredients
- Steps

Authoring interactions:

- drag reorder for equipment/ingredients/steps
- inline link insertion for step references
- metadata panel with validation warnings
- bundle eligibility toggle (export candidacy)

Current implemented baseline:

- left library panel distinguishes `[LOCAL]` vs `[BUNDLED]` recipe entries
- bundled recipes open read-only and can be duplicated into editable local copies
- center section tabs provide quick switching among Equipment/Ingredients/Steps
- library panel includes search input, scope filter, collections list, and working set quick actions
- collection operations are lightweight and recipe-centric (no duplicate content editing path)
- section editors support add/edit/delete and move up/down reordering
- metadata editor supports core fields (title/subtitle/author/source/notes/difficulty/servings/times/status)
- explicit dirty-state indicator and save action
- unsaved change prompt before switching recipes

Desktop step authoring enhancements:

- steps tab now uses selected-step detail editing (not only flat row editing)
- selected step editor includes:
  - title/body/type/estimated seconds
  - structured link list with add/edit/remove workflow
  - structured timer list with add/edit/remove workflow
- link authoring selects concrete recipe ingredient/equipment targets and writes stable link records
- step preview renders links interactively and opens target detail popups
- link and timer logic routes through a dedicated authoring service for predictable token/body synchronization

Refinement phase (authoring reuse + clarity):

- **Equipment**: desktop includes a searchable **My Equipment** picker plus inline “create global + add to recipe”; recipe lines may reference `global_equipment_id` while still allowing fully custom rows.
- **Ingredients (catalog foundation)**: default path remains **fast free-text** lines (quick add). Optional **Ingredient library** picker (desktop) and **typeahead suggestions + save to library** (desktop + mobile) link `catalog_ingredient_id` when the user chooses; typing without picking stays unlinked. Recipe lines always keep their own text as the snapshot; catalog edits never rewrite saved lines.
- **Sub-recipes (composable recipes)**: optional **“use another recipe as ingredient”** flow on desktop (**Use recipe as ingredient…**) and mobile (structured ingredient dialog). User picks a **local** recipe, **full batch** or **fraction of batch** (+ multiplier), and keeps an explicit ingredient line (e.g. “Uses 1× Béchamel”). Tooltip / subtitle text explains that grocery expands into the linked recipe’s ingredients — no hidden magic or unit conversion.
- **Steps**: optional **Advanced (optional)** block (collapsible) groups links, timers, and step image actions so new steps do not require a second pass; adding a step expands Advanced by default once to surface power features without cluttering the simple path.
- **Links (user copy)**: UI uses **Reference name** and **Display text (optional)** with short help text; values still map to internal `token_key` / `label_override`. Reference names auto-fill from the selected target until the user edits them.
- **Timers**: sound is chosen from presets (mapped internally to `alert_sound_key`); **Vibrate** is a toggle (`alert_vibrate`). Users are not asked to type raw sound keys.
- **Tags**: metadata panel supports add/remove with a combo of existing tags plus free-text new tags; library supports optional multi-tag filter (match all selected tags) without folder trees.

## Mobile UX Structure

Recipe detail uses top segmented control or tabs:

- Equipment
- Ingredients
- Steps

Execution behavior:

- Steps is default execution center
- timer definitions are visible on steps; mobile provides inline start/pause/resume/cancel plus a persistent timers strip (see “Interactive flow enhancements” below)
- quick jump back to recently opened recipe supported by local recent tracking
- sync controls exposed in dedicated tab/screen (host config, test, manual sync)

Avoid:

- giant single-scroll page containing all sections
- deeply nested step detail routes for common actions

Current implemented mobile baseline:

- app shell with Library and Sync primary destinations
- Library shows local recipe list with clear `LOCAL`/`BUNDLED` scope chips
- Library adds search + scope filter + collection chips + quick working set actions
- Recipe screen uses tab switcher for Equipment/Ingredients/Steps (not a giant scroll page)
- Steps tab is default open tab for cooking-centric flow
- Sync screen provides host URL configuration, connection test, and manual sync
- dark-mode-first theme baseline

Home surface philosophy (mobile-first):

- Home is a compact daily entry, not a dashboard.
- Sections are deterministic and stable: Today -> This Week -> Quick Resume -> light Favorites/Recent.
- Every section should support fast one-tap continuation into real work (open recipe, grocery, planner).
- Empty states stay quiet and actionable (show next best destination, no noise).

Mobile authoring parity baseline:

- Library exposes explicit create action and edit entry point for existing recipes.
- Mobile authoring uses a dedicated editor surface with tabs for Metadata/Equipment/Ingredients/Steps.
- Equipment, ingredients, and steps support add/edit/delete/reorder workflows.
- Equipment dialog supports **Pick from library** and **New library + add** (synced `global_equipment` pool); lines can show a **Linked to equipment library** hint when `global_equipment_id` is set.
- Ingredients quick-add supports **library suggestions** (tap to link) and **save typed text to the ingredient library**; list rows may show a **Library link** hint when `catalog_ingredient_id` is set. No forced catalog selection.
- Sub-recipe lines show a compact **Sub-recipe** hint on mobile; in **recipe view**, tapping a sub-recipe line opens the linked recipe when a navigator callback is available (cooking flow: lasagna → béchamel).
- Metadata **More details** includes comma-separated **Tags** (stored as `tags_json` + normalized `recipe_tags` like desktop).
- Step editing includes structured link management and structured timer management.
- Bundled recipes are shown as read-only; users must duplicate to local before editing.
- Desktop remains the faster/high-throughput authoring surface, but mobile now supports full core recipe-building capability.

Interactive flow enhancements:

- Steps render link tokens as tappable chips in-flow

Library search and filters (desktop + mobile):

- Search is **deterministic** (fixed scoring weights, title then id tie-break) and spans **title, subtitle, author, tags, ingredient lines, linked catalog names, equipment, and step text** — logic lives in **service/repository** layers, not widgets.
- **Tag filters** use **match-all** semantics (recipe must include every selected tag). Desktop: checklist under the search field. Mobile: compact **FilterChip** row (no new screen).
- **Ingredient-focused** mode (optional): only recipes where the query matches **ingredient raw text, structured name, or catalog-linked name** — useful when the user cares about “has this ingredient” more than title hits.
- Library rows may show a **short match hint** (e.g. `Ingredient · Tag`) when the query matched outside the title; kept subtle to avoid noisy badges.

Working set UX:

- surfaced as a quick mode in Library for "current focus"
- optimized for minimal taps while cooking week-to-week plans
- intentionally separate from named collections

Meal planning and grocery UX:

- mobile-first plan flow: create plan -> add recipes -> adjust servings -> generate grocery
- grocery screen uses checklist-first layout optimized for in-store use
- grouped grocery rows show quantity/unit when computable, with deterministic order for quick scanning
- desktop provides lightweight plan creation/add/generate/view actions without heavy planner UI

Calendar-aware planning UX:

- mobile planner now has week navigation and grouped-by-day schedule cards
- users can schedule meal-plan items with date + slot, or leave items unassigned for later
- mobile includes quick "today" and "this week" visibility cues
- grocery generation offers three scopes: full plan, current week, explicit date range
- desktop supports date/slot scheduling and grouped schedule viewing through lightweight dialogs
- no external calendar integration in this phase; internal schedule model is source of truth

Notifications and reminders UX (mobile-first):

- reminders are opt-in and predictable: no default spam, no hidden recurring rules
- global notifications toggle gates all local reminder scheduling
- meal items expose reminder controls (on/off + optional pre-reminder + optional start-cooking prompt)
- timer completion raises a local notification when enabled; in-app flow remains unchanged
- notification taps route users back to relevant recipe/planner context
- scheduling/cancellation happens in service/controller layers, not widget-local logic

Home sections:

- Today: meals scheduled for current day with open + mark-cooked actions.
- This Week: compact grouped upcoming schedule by day, with quick recipe open.
- Quick Resume: most recent recipe, latest grocery snapshot, active meal plan, working-set summary.
- Favorites/Recent: lightweight continuity signal without duplicating planner context.

Manual grocery editing UX:

- grocery list supports manual add, edit, delete, reorder, and checklist toggle
- visual markers distinguish generated/manual/edited rows
- regenerate action is explicit and warning-backed; it generates a new snapshot and preserves existing edited lists

Usage history / favorites UX:

- desktop library supports quick favorites and recent-opened/recent-cooked views
- desktop editor includes explicit actions: toggle favorite, mark cooked
- mobile recipe view includes favorite toggle and mark-cooked action
- mobile library exposes compact favorites + recent-opened + recent-cooked shortcuts
- signals are lightweight and intentional, avoiding noisy telemetry
- Tapping ingredient/equipment links opens bottom-sheet detail using stable `step_links.target_id`
- Missing link targets fall back to snapshot/override label and show safe missing-state detail
- Step cards show timer actions inline (start/pause/resume/cancel)
- Active timers are shown in persistent app-level strip so timers remain visible while navigating

Deferred desktop authoring items:

- advanced step-link insertion UX
- rich text editing for step bodies
- media workflows
- timer runtime controls

Deferred mobile authoring polish:

- richer inline validation/error hints inside dialogs
- faster bulk-edit interactions for very large lists
- advanced link insertion helpers while typing step body text

Deferred schedule features:

- recurring schedule rules
- drag-and-drop calendar board
- direct external calendar sync/export

Deferred notification items:

- cross-device notification sync or cloud push
- advanced quiet-hours/rule-builder engine
- rich desktop OS notification center integration

Home non-goals:

- recommendation engines or AI ranking
- analytics-heavy dashboard metrics
- alert/notification center

Media UX baseline:

- desktop supports lightweight attach/remove actions for recipe cover and step images
- mobile authoring supports staged path-based cover/step image attachment in editor dialogs
- mobile recipe view displays cover/step images when local files exist
- library shows a visual cover indicator and attempts thumbnail render when available
- missing media files show explicit fallback text instead of silent failure

Deferred media polish:

- native gallery/camera pickers with richer permissions UX
- image editing/cropping pipeline
- multi-image galleries per entity

## First-use and low-friction UX

Philosophy:

- Prefer one or two obvious next actions over explanation walls.
- Keep advanced authoring (links, timers, structured ingredient rows) available but visually secondary until the user expands it.
- Empty states stay short: what it means plus the best next tap.

Empty states:

- Mobile Home shows a compact “Get started” card only when the dashboard is effectively empty (`looksLikeFirstVisit`), with Create recipe, Plan a meal, and Library.
- Library, Planner, and Grocery use brief copy and at most two primary actions (for example create vs sync, or plan vs pick recipe).
- Desktop library shows an inline hint above the list when there are no recipes or no filter matches.

Recipe creation hierarchy:

- Title (recipe name) and notes are “start here”; other metadata lives under an explicit optional group (desktop: “More details (optional)” group box; mobile: collapsed “More details” on the Meta tab).
- Cover image actions stay with optional metadata so the first save path stays light.

Ingredient entry:

- Default path is a single free-text line (for example “2 cups flour”); structured quantity, unit, and name remain available via “Structured row” or table columns, not required up front.

Advanced step features:

- Links, timers, and step images are grouped under optional copy and collapsible sections so new users see instructions first.

Meal planning defaults:

- Default meal slot is dinner; the slot picker order leads with dinner.
- Quick schedule emphasizes recipe, date, and save; slot, servings, and reminders sit behind “Meal time & reminders” (collapsed by default). A Today control sets the date without opening the picker first.
- Planner notification toggles and reminder defaults are under a collapsed “Reminders & defaults” area so the common path stays fast.

Share and media messaging:

- Export or share of recipes that include photos or other media is blocked with a calm, explicit message: attachments are not included yet, so export was stopped on purpose. The same idea is surfaced on import errors for media-bearing packages.
- No silent failure: users always see why export did not proceed.

Backup trust (quiet):

- About and Diagnostics mention that backups exist and where they live; mobile Sync includes a one-line note pointing at desktop backup zip. No banners or nag dialogs.

