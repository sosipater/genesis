# Idea backlog and future directions

This document captures **strategic product and architecture ideas** that must not be lost. It is **not** a commitment to build everything listed, nor a prioritized sprint backlog. For dependency-ordered delivery, see `docs/09_ROADMAP.md`.

## Product principles (carry forward)

- **Local-first** storage; cloud is optional in future, not assumed.
- **Structured data** with stable IDs, versioned schemas, explicit sync/backup/share contracts.
- **Reusable entities** where it reduces duplication and improves consistency (equipment, ingredients, later “knowledge” artifacts).
- **Calm UX**: power features exist but stay behind progressive disclosure, settings, or compact surfaces.
- **Mobile and desktop parity** for core create/edit/sync capability; desktop may remain higher-throughput, not exclusive.
- **Sync-safe, backup-safe, share-safe**: no silent destructive merges; portable packages stay deterministic.

## Naming and long-term scope

- The codebase and repo are branded **Genesis**; **Recipe Forge** is an equivalent product name in some materials.
- Recipes remain the **primary user concept** for the foreseeable future.
- Architecture should stay compatible with broader **procedural knowledge** (checklists, workflows beyond cooking) **without** renaming the core model to “procedures” prematurely.

---

## Idea clusters (source list)

### 1. Reusable equipment pool

**Intent:** Users define equipment once (notes, media, affiliate links, comparisons) and reuse across recipes; recipe lines keep snapshot fields where needed.

**Current state:** Desktop and **mobile** implement `global_equipment`, `recipe_equipment.global_equipment_id`, sync entity `global_equipment`, and mobile equipment editor flows to pick or create library items. Normalized **tags** / `recipe_tags` / `tags_json` and `step_timers.alert_vibrate` are also aligned on mobile **schema v11**. **Ingredient catalog groundwork** (`catalog_ingredient`, `recipe_ingredients.catalog_ingredient_id`, sync `catalog_ingredient`, lightweight pick/suggest/save UX) ships at **schema v12** — still **not** a nutrition or media-heavy catalog.

**Classification:** **Near-term / implement next** (parity + polish), not greenfield.

---

### 2. Ingredient catalog / reusable ingredient entities

**Intent:** Ingredients can be ad hoc (today) or linked to a **catalog entity** (storage notes, image, future nutrition, etc.); supports richer authoring and future bulk/Excel workflows.

**Current state (foundation):** `catalog_ingredient` exists with optional `recipe_ingredients.catalog_ingredient_id`; recipe lines keep **snapshot text**; sync includes `catalog_ingredient` upserts/tombstones; desktop/mobile have minimal library pick, typeahead suggestions, and save-to-library — **no** nutrition fields, **no** unit conversion, **no** management console.

**Classification:** **Deeper catalog features** (nutrition, media, aliases UI, bulk edit) remain **defer** until the link model is exercised; foundation is aligned with equipment reuse patterns.

---

### 3. Sub-recipe references / composable recipes

**Intent:** Recipe A references Recipe B as a component (e.g. lasagna → béchamel), likely as **full-batch or explicit fraction-of-batch**, not magic unit conversion.

**Current state (first slice, in tree):** explicit `full_batch` / `fraction_of_batch` (+ multiplier), recursive grocery expansion with cycle + depth limits, share closure + atomic import validation, desktop + mobile authoring, recipe-view navigation to linked recipe. **Still defer:** arbitrary unit conversion (“1 cup of sauce”), cross-package share references without bundling, rich dependency graphs.

---

### 4. Organization (tags, light grouping)

**Intent:** Stronger tags and light containers/categories; search across tags, titles, ingredient names; avoid deep nested folder trees unless a clear user need appears.

**Current state:** Desktop has normalized `tags` + `recipe_tags` + library filters. Mobile alignment is part of schema/parity work with equipment.

**Classification:** **Near-term** alongside reusable-entity parity; **defer** deep hierarchy UX.

---

### 5. Excel import/export / spreadsheet workflows

**Intent:** Power-user and AI-assisted bulk edit for catalog and possibly recipe tables.

**Classification:** **Defer intentionally** as a **layer beside** core UX, not a replacement; depends on catalog + stable export contracts.

---

### 6. Configurable theme / settings philosophy

**Intent:** Settings stay consolidated; **theme/color** configurable when color is not semantically load-bearing.

**Classification:** **Mid-term polish**; no blocking dependency for data model work.

---

### 7. Media scale strategy

**Intent:** Local images remain in managed storage; **video / very large assets** may need streaming or online strategy later.

**Classification:** **Document and defer** implementation; capture constraints in roadmap (see `09_ROADMAP.md`). Do not block current local-image model.

---

### 8. Sharing as portable knowledge

**Intent:** Recipes, equipment, and future packs stay **data-first**, deterministic, versioned share formats.

**Classification:** **Ongoing constraint** on all features; extend formats deliberately when adding new entity types.

---

## Quick classification table

| Cluster | Implement next | Foundation first | Defer |
|---------------------|----------------|------------------|-------|
| Reusable equipment | ● (mobile parity) |                  |       |
| Ingredient catalog |                | ●                |       |
| Sub-recipes        |                |                  | ● |
| Tags / organization| ● (parity)     |                  | deep trees |
| Excel workflows    |                |                  | ●     |
| Theme / settings   |                |                  | polish |
| Media at scale     |                |                  | ● doc |
| Portable sharing   | constraint |                  |       |
