# Content Packaging Strategy

## Separation Contract

Bundled content and local content are separated by storage and lifecycle:

- `bundled_content/` contains release-managed app content package.
- local DB contains user-owned editable recipes and related entities.

No runtime update path may overwrite local user records from bundled updates.

## Share Package Path (User Import/Export)

Share packages are a third path, separate from bundled and normal local editing:

1. Bundled content (release-managed, read-only)
2. Local recipes (user-owned, editable)
3. Share packages (portable exchange/backup format importing into local scope)

Share packages do **not** become bundled content automatically.

## Bundle Layout

- `bundled_content/manifest.json`
- `bundled_content/recipes/*.json`
- `bundled_content/media/*`
- `bundled_content/affiliates/*`

## Manifest Responsibilities

- declare `manifest_version` and `app_content_version`
- list bundled recipe IDs and file paths
- include checksums for integrity
- include migration notes for bundle evolution

## Authoring to Bundle Flow

1. User creates/edits local recipe.
2. User marks recipe as `bundle_export_eligible`.
3. Export workflow assigns/uses stable `export_bundle_recipe_id` for each eligible recipe.
4. Tool emits bundled recipe JSON files under `bundled_content/recipes/`.
5. Tool computes checksums and writes deterministic `bundled_content/manifest.json`.
6. Local recipe metadata is updated with export provenance fields (without changing ownership semantics).
5. Package is shipped in a release.

Desktop export surfaces success/failure and keeps standard recipe editing separate from package generation.

## Provenance and Fork Metadata

Local recipes now track packaging/fork provenance:

- `export_bundle_recipe_id`: stable packaged bundled ID assigned to exported local recipe
- `export_bundle_recipe_version`: bundled recipe version from export pipeline
- `origin_bundled_recipe_id`: bundled source ID when local recipe is duplicated from bundled
- `origin_bundled_recipe_version`: bundled version used at fork time
- `is_forked_from_bundled`: local fork marker

These fields support future compare/merge UX while preserving strict local ownership.

## Update Safety Rules

- Bundled recipe updates replace bundled package content only.
- Local forks remain unchanged and editable.
- Bundled updates do not overwrite local recipes, including local forks.
- Local forks retain origin metadata for future user-driven comparison workflows.

## Manifest Hardening

Manifest entries include:

- bundled recipe ID
- bundled recipe version
- path to recipe file
- checksum
- title snapshot
- optional source local recipe ID

Validation checks enforce:

- schema validity
- duplicate bundled ID rejection
- recipe file existence
- checksum integrity
- recipe payload/manifest ID consistency
- link target integrity within bundled recipe files
- orphaned bundled recipe files not present in manifest

## Diff and Change Insight Tooling

Structured diff tooling supports:

- bundled recipe version-to-version comparison
- local fork vs bundled origin comparison
- file-to-file recipe comparison

Diff model is deterministic and ID-based, reporting:

- added/removed/modified entities
- field-level before/after values
- explicit ordering changes

Export pipeline uses diff output to provide non-blocking safety warnings for unexpectedly large removals and required equipment removal.

## Share Format

Portable JSON package (`.json`) structure:

- `share_format_version`
- `package_id`
- `exported_at_utc`
- `source_app`
- `media_included` (currently `false`)
- `recipes[]` (full structured recipe payloads with equipment/ingredients/steps/links/timers)

Format goals:

- deterministic structure
- easy portability
- schema validation support
- forward-compatible version field

## Share Export Rules

- only local recipes are exportable in share workflow
- export never mutates recipe ownership semantics
- stable IDs are preserved inside package payload
- bundled recipes are not exported as user-owned bundled content
- recipes with media attachments are currently rejected for share export (explicit error; no silent media drop)

## Share Import Rules

- imported recipes are always local editable recipes
- import validation runs before persistence (package + recipe schema + graph model validation)
- no silent overwrite of existing local records
- collision handling is safe and deterministic:
  - import always remaps to new local recipe/child IDs
  - repeated import of same package recipe is skipped via import provenance key
  - collisions are reported in import summary
- packages that contain media references are currently rejected (media transport deferred)

## Media Sync / Packaging Decision (Current Phase)

- media metadata sync is supported (`media_asset` entities and `*_media_id` references)
- media file transfer over LAN sync is deferred
- bundled/share packaging does not include media binaries yet
- UX must surface missing-media fallback when metadata references files that are unavailable locally

## Mobile Strategy

Current phase chooses desktop-first import/export:

- desktop supports import/export UI and CLI tools
- mobile consumes imported recipes via existing local/sync flows
- direct mobile file import/export is deferred to avoid file-handling complexity in this phase

## Bundled Forking Behavior

- user can duplicate bundled recipe into local scope
- local duplicate gets new local recipe ID
- local duplicate is tagged with bundled origin metadata
- future bundled updates affect only bundled record, not fork

## Desktop Operational Backup Package

Operational backup is intentionally separate from bundled and share packaging:

- format: zip archive containing `manifest.json`
- payload includes:
  - desktop local DB file
  - managed media files
  - local desktop preferences file when present
- validation requires manifest presence and checksum/size match for each archived file
- restore path is explicit full replace only in this phase (`allow_replace=true`)

Backup package exclusions:

- bundled content source tree
- remote/cloud state (none in current architecture)
- mobile private app storage

