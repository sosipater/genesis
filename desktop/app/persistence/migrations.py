"""SQLite migration runner with schema version tracking."""

from __future__ import annotations

import sqlite3
from typing import Callable


def _migration_v1(conn: sqlite3.Connection, now_iso: str) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS local_recipes (
          id TEXT PRIMARY KEY,
          payload_json TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS sync_state (
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          entity_updated_at TEXT NOT NULL,
          last_modified_device_id TEXT NOT NULL,
          last_synced_at TEXT NULL,
          sync_version INTEGER NOT NULL,
          is_tombstone INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(entity_type, entity_id)
        );

        CREATE TABLE IF NOT EXISTS sync_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id TEXT NOT NULL,
          session_id TEXT NOT NULL,
          device_id TEXT NOT NULL,
          direction TEXT NOT NULL,
          status TEXT NOT NULL,
          summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sync_conflicts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          incoming_updated_at TEXT NOT NULL,
          local_updated_at TEXT NOT NULL,
          incoming_device_id TEXT NOT NULL,
          incoming_entity_version INTEGER NULL,
          local_entity_version INTEGER NULL,
          resolution TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )


def _migration_v2(conn: sqlite3.Connection, now_iso: str) -> None:
    import json

    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS recipes (
          id TEXT PRIMARY KEY,
          scope TEXT NOT NULL CHECK(scope = 'local'),
          schema_version INTEGER NOT NULL DEFAULT 1,
          bundled_content_version TEXT NULL,
          bundle_export_eligible INTEGER NOT NULL DEFAULT 0,
          export_bundle_recipe_id TEXT NULL,
          export_bundle_recipe_version INTEGER NOT NULL DEFAULT 1,
          origin_bundled_recipe_id TEXT NULL,
          origin_bundled_recipe_version INTEGER NULL,
          is_forked_from_bundled INTEGER NOT NULL DEFAULT 0,
          title TEXT NOT NULL,
          subtitle TEXT NULL,
          author TEXT NULL,
          source_name TEXT NULL,
          source_url TEXT NULL,
          tags_json TEXT NOT NULL DEFAULT '[]',
          category TEXT NULL,
          difficulty TEXT NULL,
          servings REAL NULL,
          prep_minutes INTEGER NULL,
          cook_minutes INTEGER NULL,
          total_minutes INTEGER NULL,
          notes TEXT NULL,
          cover_media_id TEXT NULL,
          display_settings_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS media_assets (
          id TEXT PRIMARY KEY,
          owner_type TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          local_path TEXT NULL,
          bundled_path TEXT NULL,
          mime_type TEXT NOT NULL,
          width INTEGER NULL,
          height INTEGER NULL,
          checksum_sha256 TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS recipe_equipment (
          id TEXT PRIMARY KEY,
          recipe_id TEXT NOT NULL,
          name TEXT NOT NULL,
          description TEXT NULL,
          why_used TEXT NULL,
          is_required INTEGER NOT NULL,
          notes TEXT NULL,
          affiliate_url TEXT NULL,
          alternate_equipment_text TEXT NULL,
          media_id TEXT NULL,
          display_order INTEGER NOT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL,
          FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
          FOREIGN KEY(media_id) REFERENCES media_assets(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS recipe_ingredients (
          id TEXT PRIMARY KEY,
          recipe_id TEXT NOT NULL,
          raw_text TEXT NOT NULL,
          quantity_value REAL NULL,
          quantity_text TEXT NULL,
          unit TEXT NULL,
          ingredient_name TEXT NULL,
          preparation_notes TEXT NULL,
          substitutions TEXT NULL,
          affiliate_url TEXT NULL,
          recommended_product TEXT NULL,
          media_id TEXT NULL,
          is_optional INTEGER NOT NULL,
          display_order INTEGER NOT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL,
          FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
          FOREIGN KEY(media_id) REFERENCES media_assets(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS recipe_steps (
          id TEXT PRIMARY KEY,
          recipe_id TEXT NOT NULL,
          title TEXT NULL,
          body_text TEXT NOT NULL,
          display_order INTEGER NOT NULL,
          step_type TEXT NOT NULL,
          estimated_seconds INTEGER NULL,
          media_id TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL,
          FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
          FOREIGN KEY(media_id) REFERENCES media_assets(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS step_links (
          id TEXT PRIMARY KEY,
          step_id TEXT NOT NULL,
          target_type TEXT NOT NULL,
          target_id TEXT NOT NULL,
          token_key TEXT NOT NULL,
          label_snapshot TEXT NOT NULL,
          label_override TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL,
          FOREIGN KEY(step_id) REFERENCES recipe_steps(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS step_timers (
          id TEXT PRIMARY KEY,
          step_id TEXT NOT NULL,
          label TEXT NOT NULL,
          duration_seconds INTEGER NOT NULL,
          auto_start INTEGER NOT NULL,
          alert_sound_key TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL,
          FOREIGN KEY(step_id) REFERENCES recipe_steps(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_recipes_updated_at ON recipes(updated_at);
        CREATE INDEX IF NOT EXISTS idx_equipment_recipe ON recipe_equipment(recipe_id, display_order);
        CREATE INDEX IF NOT EXISTS idx_ingredients_recipe ON recipe_ingredients(recipe_id, display_order);
        CREATE INDEX IF NOT EXISTS idx_steps_recipe ON recipe_steps(recipe_id, display_order);
        CREATE INDEX IF NOT EXISTS idx_links_step ON step_links(step_id);
        CREATE INDEX IF NOT EXISTS idx_timers_step ON step_timers(step_id);
        """
    )

    local_recipes_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='local_recipes'"
    ).fetchone()
    if local_recipes_exists is None:
        return

    rows = conn.execute("SELECT id, payload_json FROM local_recipes ORDER BY updated_at").fetchall()
    for row in rows:
        payload = json.loads(row["payload_json"])
        created_at = payload["created_at"]
        updated_at = payload["updated_at"]
        deleted_at = payload.get("deleted_at")
        conn.execute(
            """
            INSERT OR REPLACE INTO recipes(
              id, scope, schema_version, bundled_content_version, bundle_export_eligible,
              export_bundle_recipe_id, export_bundle_recipe_version, origin_bundled_recipe_id, origin_bundled_recipe_version, is_forked_from_bundled,
              title, subtitle, author, source_name, source_url, tags_json, category, difficulty, servings,
              prep_minutes, cook_minutes, total_minutes, notes, cover_media_id, display_settings_json, status,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, 'local', ?, ?, ?, NULL, 1, NULL, NULL, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                payload["id"],
                payload.get("schema_version", 1),
                payload.get("bundled_content_version"),
                int(payload.get("bundle_export_eligible", False)),
                payload["title"],
                payload.get("subtitle"),
                payload.get("author"),
                payload.get("source_name"),
                payload.get("source_url"),
                json.dumps(payload.get("tags", [])),
                payload.get("category"),
                payload.get("difficulty"),
                payload.get("servings"),
                payload.get("prep_minutes"),
                payload.get("cook_minutes"),
                payload.get("total_minutes"),
                payload.get("notes"),
                payload.get("cover_media_id"),
                json.dumps(payload.get("display_settings", {})),
                payload["status"],
                created_at,
                updated_at,
                deleted_at,
            ),
        )

        for item in payload.get("equipment", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO recipe_equipment(
                  id, recipe_id, name, description, why_used, is_required, notes, affiliate_url,
                  alternate_equipment_text, media_id, display_order, entity_version, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    item["id"],
                    payload["id"],
                    item["name"],
                    item.get("description"),
                    item.get("why_used"),
                    int(item["is_required"]),
                    item.get("notes"),
                    item.get("affiliate_url"),
                    item.get("alternate_equipment_text"),
                    item.get("media_id"),
                    item["display_order"],
                    created_at,
                    updated_at,
                    deleted_at,
                ),
            )

        for item in payload.get("ingredients", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO recipe_ingredients(
                  id, recipe_id, raw_text, quantity_value, quantity_text, unit, ingredient_name,
                  preparation_notes, substitutions, affiliate_url, recommended_product, media_id,
                  is_optional, display_order, entity_version, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    item["id"],
                    payload["id"],
                    item["raw_text"],
                    item.get("quantity_value"),
                    item.get("quantity_text"),
                    item.get("unit"),
                    item.get("ingredient_name"),
                    item.get("preparation_notes"),
                    item.get("substitutions"),
                    item.get("affiliate_url"),
                    item.get("recommended_product"),
                    item.get("media_id"),
                    int(item["is_optional"]),
                    item["display_order"],
                    created_at,
                    updated_at,
                    deleted_at,
                ),
            )

        for step in payload.get("steps", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO recipe_steps(
                  id, recipe_id, title, body_text, display_order, step_type, estimated_seconds, media_id,
                  entity_version, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    step["id"],
                    payload["id"],
                    step.get("title"),
                    step["body_text"],
                    step["display_order"],
                    step["step_type"],
                    step.get("estimated_seconds"),
                    step.get("media_id"),
                    created_at,
                    updated_at,
                    deleted_at,
                ),
            )

            for timer in step.get("timers", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO step_timers(
                      id, step_id, label, duration_seconds, auto_start, alert_sound_key,
                      entity_version, created_at, updated_at, deleted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        timer["id"],
                        step["id"],
                        timer["label"],
                        timer["duration_seconds"],
                        int(timer["auto_start"]),
                        timer.get("alert_sound_key"),
                        created_at,
                        updated_at,
                        deleted_at,
                    ),
                )

        for link in payload.get("step_links", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO step_links(
                  id, step_id, target_type, target_id, token_key, label_snapshot, label_override,
                  entity_version, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    link["id"],
                    link["step_id"],
                    link["target_type"],
                    link["target_id"],
                    link["token_key"],
                    link["label_snapshot"],
                    link.get("label_override"),
                    created_at,
                    updated_at,
                    deleted_at,
                ),
            )

    conn.execute("DROP TABLE local_recipes")
    conn.commit()


def _migration_v3(conn: sqlite3.Connection, now_iso: str) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(recipes)").fetchall()}
    if "export_bundle_recipe_id" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN export_bundle_recipe_id TEXT NULL")
    if "export_bundle_recipe_version" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN export_bundle_recipe_version INTEGER NOT NULL DEFAULT 1")
    if "origin_bundled_recipe_id" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN origin_bundled_recipe_id TEXT NULL")
    if "origin_bundled_recipe_version" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN origin_bundled_recipe_version INTEGER NULL")
    if "is_forked_from_bundled" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN is_forked_from_bundled INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def _migration_v4(conn: sqlite3.Connection, now_iso: str) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS collections (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          deleted_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS collection_items (
          id TEXT PRIMARY KEY,
          collection_id TEXT NOT NULL,
          recipe_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          deleted_at TEXT NULL,
          UNIQUE(collection_id, recipe_id),
          FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS working_set_items (
          id TEXT PRIMARY KEY,
          recipe_id TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_collection_items_collection ON collection_items(collection_id);
        CREATE INDEX IF NOT EXISTS idx_working_set_active ON working_set_items(deleted_at);
        """
    )
    conn.commit()


def _migration_v5(conn: sqlite3.Connection, now_iso: str) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meal_plans (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          start_date TEXT NULL,
          end_date TEXT NULL,
          notes TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS meal_plan_items (
          id TEXT PRIMARY KEY,
          meal_plan_id TEXT NOT NULL,
          recipe_id TEXT NOT NULL,
          servings_override REAL NULL,
          notes TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL,
          FOREIGN KEY(meal_plan_id) REFERENCES meal_plans(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS grocery_lists (
          id TEXT PRIMARY KEY,
          meal_plan_id TEXT NULL,
          name TEXT NOT NULL,
          generated_at TEXT NOT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS grocery_list_items (
          id TEXT PRIMARY KEY,
          grocery_list_id TEXT NOT NULL,
          name TEXT NOT NULL,
          quantity_value REAL NULL,
          unit TEXT NULL,
          checked INTEGER NOT NULL DEFAULT 0,
          source_recipe_ids_json TEXT NOT NULL DEFAULT '[]',
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL,
          FOREIGN KEY(grocery_list_id) REFERENCES grocery_lists(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_meal_plan_items_plan ON meal_plan_items(meal_plan_id);
        CREATE INDEX IF NOT EXISTS idx_grocery_items_list ON grocery_list_items(grocery_list_id);
        """
    )
    conn.commit()


def _migration_v6(conn: sqlite3.Connection, now_iso: str) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(grocery_list_items)").fetchall()}
    if "source_type" not in columns:
        conn.execute("ALTER TABLE grocery_list_items ADD COLUMN source_type TEXT NOT NULL DEFAULT 'generated'")
    if "generated_group_key" not in columns:
        conn.execute("ALTER TABLE grocery_list_items ADD COLUMN generated_group_key TEXT NULL")
    if "was_user_modified" not in columns:
        conn.execute("ALTER TABLE grocery_list_items ADD COLUMN was_user_modified INTEGER NOT NULL DEFAULT 0")
    if "sort_order" not in columns:
        conn.execute("ALTER TABLE grocery_list_items ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def _migration_v7(conn: sqlite3.Connection, now_iso: str) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS recipe_user_state (
          recipe_id TEXT PRIMARY KEY,
          is_favorite INTEGER NOT NULL DEFAULT 0,
          last_opened_at TEXT NULL,
          last_cooked_at TEXT NULL,
          open_count INTEGER NOT NULL DEFAULT 0,
          cook_count INTEGER NOT NULL DEFAULT 0,
          pinned INTEGER NOT NULL DEFAULT 0,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_recipe_user_state_favorite ON recipe_user_state(is_favorite, updated_at);
        CREATE INDEX IF NOT EXISTS idx_recipe_user_state_opened ON recipe_user_state(last_opened_at);
        CREATE INDEX IF NOT EXISTS idx_recipe_user_state_cooked ON recipe_user_state(last_cooked_at);
        """
    )
    conn.commit()


def _migration_v8(conn: sqlite3.Connection, now_iso: str) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(recipes)").fetchall()}
    if "imported_from_package_id" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN imported_from_package_id TEXT NULL")
    if "imported_from_recipe_id" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN imported_from_recipe_id TEXT NULL")
    if "imported_at" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN imported_at TEXT NULL")
    if "import_source_label" not in columns:
        conn.execute("ALTER TABLE recipes ADD COLUMN import_source_label TEXT NULL")
    conn.commit()


def _migration_v9(conn: sqlite3.Connection, now_iso: str) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(meal_plan_items)").fetchall()}
    if "planned_date" not in columns:
        conn.execute("ALTER TABLE meal_plan_items ADD COLUMN planned_date TEXT NULL")
    if "meal_slot" not in columns:
        conn.execute("ALTER TABLE meal_plan_items ADD COLUMN meal_slot TEXT NULL")
    if "slot_label" not in columns:
        conn.execute("ALTER TABLE meal_plan_items ADD COLUMN slot_label TEXT NULL")
    if "sort_order" not in columns:
        conn.execute("ALTER TABLE meal_plan_items ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def _migration_v10(conn: sqlite3.Connection, now_iso: str) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(media_assets)").fetchall()}
    if "file_name" not in columns:
        conn.execute("ALTER TABLE media_assets ADD COLUMN file_name TEXT NULL")
    if "relative_path" not in columns:
        conn.execute("ALTER TABLE media_assets ADD COLUMN relative_path TEXT NULL")
    conn.commit()


def _migration_v11(conn: sqlite3.Connection, now_iso: str) -> None:
    import json
    from uuid import uuid4

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS global_equipment (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          notes TEXT NULL,
          media_id TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_global_equipment_updated ON global_equipment(updated_at);

        CREATE TABLE IF NOT EXISTS tags (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL COLLATE NOCASE UNIQUE,
          color TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tags_updated ON tags(updated_at);

        CREATE TABLE IF NOT EXISTS recipe_tags (
          recipe_id TEXT NOT NULL,
          tag_id TEXT NOT NULL,
          PRIMARY KEY (recipe_id, tag_id),
          FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
          FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
        """
    )
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(recipe_equipment)").fetchall()}
    if "global_equipment_id" not in cols:
        conn.execute("ALTER TABLE recipe_equipment ADD COLUMN global_equipment_id TEXT NULL")
    cols_t = {row["name"] for row in conn.execute("PRAGMA table_info(step_timers)").fetchall()}
    if "alert_vibrate" not in cols_t:
        conn.execute("ALTER TABLE step_timers ADD COLUMN alert_vibrate INTEGER NOT NULL DEFAULT 0")
    conn.commit()

    for row in conn.execute("SELECT id, tags_json FROM recipes WHERE deleted_at IS NULL").fetchall():
        rid = row["id"]
        try:
            names = json.loads(row["tags_json"] or "[]")
        except json.JSONDecodeError:
            continue
        if not isinstance(names, list):
            continue
        for raw in names:
            if not raw or not str(raw).strip():
                continue
            name_clean = str(raw).strip()
            cur = conn.execute(
                "SELECT id FROM tags WHERE lower(name) = lower(?) AND deleted_at IS NULL",
                (name_clean,),
            ).fetchone()
            if cur:
                tid = cur["id"]
            else:
                tid = str(uuid4())
                conn.execute(
                    """
                    INSERT INTO tags(id, name, color, entity_version, created_at, updated_at, deleted_at)
                    VALUES(?,?,NULL,1,?,?,NULL)
                    """,
                    (tid, name_clean, now_iso, now_iso),
                )
            conn.execute("INSERT OR IGNORE INTO recipe_tags(recipe_id, tag_id) VALUES(?,?)", (rid, tid))
    conn.commit()


def _migration_v12(conn: sqlite3.Connection, now_iso: str) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_ingredient (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          normalized_name TEXT NOT NULL,
          notes TEXT NULL,
          entity_version INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_catalog_ingredient_updated ON catalog_ingredient(updated_at);
        CREATE INDEX IF NOT EXISTS idx_catalog_ingredient_normalized ON catalog_ingredient(normalized_name);
        """
    )
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(recipe_ingredients)").fetchall()}
    if "catalog_ingredient_id" not in cols:
        conn.execute("ALTER TABLE recipe_ingredients ADD COLUMN catalog_ingredient_id TEXT NULL")
    conn.commit()


def _migration_v13(conn: sqlite3.Connection, now_iso: str) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(recipe_ingredients)").fetchall()}
    if "sub_recipe_id" not in cols:
        conn.execute("ALTER TABLE recipe_ingredients ADD COLUMN sub_recipe_id TEXT NULL")
    if "sub_recipe_usage_type" not in cols:
        conn.execute("ALTER TABLE recipe_ingredients ADD COLUMN sub_recipe_usage_type TEXT NULL")
    if "sub_recipe_multiplier" not in cols:
        conn.execute("ALTER TABLE recipe_ingredients ADD COLUMN sub_recipe_multiplier REAL NULL")
    if "sub_recipe_display_name" not in cols:
        conn.execute("ALTER TABLE recipe_ingredients ADD COLUMN sub_recipe_display_name TEXT NULL")
    conn.commit()


MIGRATIONS: dict[int, Callable[[sqlite3.Connection, str], None]] = {
    1: _migration_v1,
    2: _migration_v2,
    3: _migration_v3,
    4: _migration_v4,
    5: _migration_v5,
    6: _migration_v6,
    7: _migration_v7,
    8: _migration_v8,
    9: _migration_v9,
    10: _migration_v10,
    11: _migration_v11,
    12: _migration_v12,
    13: _migration_v13,
}


def apply_migrations(conn: sqlite3.Connection, now_iso: str) -> int:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );
        """
    )
    current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
        MIGRATIONS[version](conn, now_iso)
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
            (version, now_iso),
        )
        conn.commit()
        current = version
    return current

