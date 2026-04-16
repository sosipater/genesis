# Product Requirements

## Core Recipe Object

Required top-level metadata:

- title, subtitle, author
- source_name, source_url
- tags, category, difficulty
- servings, prep/cook/total minutes
- notes, optional cover image
- scope (`bundled` or `local`)
- created/updated timestamps
- optional display settings

## Core Content Sections

Every recipe has:

1. Equipment list
2. Ingredient list
3. Step flow

Desktop and mobile must provide fast section switching with no deep navigation dependence.

## Equipment Requirements

- minimal item creation with optional detailed expansion
- required/optional flag
- alternative equipment + affiliate metadata
- optional media, notes, display order
- step-linkable via stable IDs

## Ingredient Requirements

- supports both simple (`salt`) and structured (`2 tsp kosher salt`) entry
- preserve raw human expression (`raw_text`) even when structured fields are present
- optional substitutions, preparation notes, affiliate data, media
- step-linkable via stable IDs
- optional **sub-recipe** reference: another recipe as a component (`full_batch` or `fraction_of_batch` with explicit multiplier), with predictable grocery expansion and explicit share/export rules (no hidden unit conversion)

## Step/Flow Requirements

- easy create and reorder
- rich/semi-rich instruction text
- inline references to equipment/ingredients
- zero-to-many timers per step
- practical guided cooking UX on mobile

## Timer Requirements

- start/pause/resume/cancel/complete
- persistent state independent from UI widgets
- active timer visibility while navigating
- safe behavior on sleep/reopen
- mvp persistence is device-local; sync of active states is optional and explicit

## Sync Requirements (MVP)

- LAN desktop-hosted HTTP sync
- protocol versioning and schema-aware payloads
- health endpoint + sync probe endpoint
- conflict handling without silent destructive merges
- structured logging with correlation IDs

## Scope Separation Requirements

- bundled app content and local user content are physically/logically separated
- bundled updates are versioned and additive/safe
- local editable content is never overwritten by bundle refresh
- bundled-to-local duplication creates independent local copy

