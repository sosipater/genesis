# Test Strategy

## Testing Layers

- **Unit tests**: domain invariants, parser/formatter behavior, timer state transitions.
- **Persistence tests**: schema migrations, repository CRUD, tombstone behavior.
- **Contract tests**: sync envelope validation, endpoint response shapes.
- **Bundle tests**: manifest validity, recipe schema checks, checksum verification.
- **Integration tests**: desktop host + mobile sync client scenario playback.

## Priority Coverage (MVP)

1. Recipe schema validation for local and bundled payloads.
2. Step reference token parsing and missing-target fallback rendering.
3. Sync pull/push idempotency and conflict annotation behavior.
4. Migration safety tests for SQLite schema version updates.
5. Timer engine transitions independent from UI lifecycle.

## Automation Approach

- `pytest` for Python desktop/tools/shared contract tests (`pyproject.toml` sets `testpaths` to `desktop/tests` and `tests`)
- Flutter `test` for mobile domain/data/sync modules
- fixture-driven sync transcript tests under `tests/contracts`

## Desktop regression highlights

- `desktop/tests/test_refinement_phase.py` covers global equipment persistence, `recipe_tags` alignment, timer `alert_vibrate` roundtrip, sound preset mapping, and tag-based library filters.
- `desktop/tests/test_meal_plan_grocery_service.py` covers sub-recipe grocery expansion (full batch, fraction, cycles, missing refs, repository round-trip).
- `desktop/tests/test_recipe_share_service.py` covers share export transitive closure and orphan sub-recipe import rejection (requires `jsonschema` for collection).

## Regression Guardrails

- block merge if schema validators fail
- block merge if manifest validator fails
- include representative medium-sized recipe fixtures for performance profiling

