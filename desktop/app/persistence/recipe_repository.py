"""Repository for normalized local recipe CRUD operations."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
import json
from uuid import uuid4

from desktop.app.domain.models import (
    Recipe,
    RecipeEquipmentItem,
    RecipeIngredientItem,
    RecipeStep,
    StepLink,
    StepTimer,
    utc_now_iso,
)


def _normalize_catalog_ingredient_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


class RecipeRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create_recipe(self, recipe: Recipe) -> None:
        recipe.validate()
        if recipe.scope != "local":
            raise ValueError("RecipeRepository only accepts local scope recipes")
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO recipes(
                  id, scope, schema_version, bundled_content_version, bundle_export_eligible,
                  export_bundle_recipe_id, export_bundle_recipe_version, origin_bundled_recipe_id, origin_bundled_recipe_version, is_forked_from_bundled,
                  imported_from_package_id, imported_from_recipe_id, imported_at, import_source_label,
                  title, subtitle, author, source_name, source_url, tags_json, category, difficulty,
                  servings, prep_minutes, cook_minutes, total_minutes, notes, cover_media_id,
                  display_settings_json, status, entity_version, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe.id,
                    "local",
                    recipe.schema_version,
                    recipe.bundled_content_version,
                    int(recipe.bundle_export_eligible),
                    recipe.export_bundle_recipe_id,
                    recipe.export_bundle_recipe_version,
                    recipe.origin_bundled_recipe_id,
                    recipe.origin_bundled_recipe_version,
                    int(recipe.is_forked_from_bundled),
                    recipe.imported_from_package_id,
                    recipe.imported_from_recipe_id,
                    recipe.imported_at,
                    recipe.import_source_label,
                    recipe.title,
                    recipe.subtitle,
                    recipe.author,
                    recipe.source_name,
                    recipe.source_url,
                    json.dumps(recipe.tags),
                    recipe.category,
                    recipe.difficulty,
                    recipe.servings,
                    recipe.prep_minutes,
                    recipe.cook_minutes,
                    recipe.total_minutes,
                    recipe.notes,
                    recipe.cover_media_id,
                    json.dumps(recipe.display_settings),
                    recipe.status,
                    1,
                    recipe.created_at,
                    recipe.updated_at,
                    recipe.deleted_at,
                ),
            )
            self._replace_children(recipe, for_update=False)
            self._sync_recipe_tags(recipe.id, recipe.tags, recipe.updated_at)
            self._upsert_sync_state("recipe", recipe.id, recipe.updated_at, "desktop-local", is_tombstone=False)

    def update_recipe(self, recipe: Recipe) -> None:
        recipe.validate()
        if recipe.scope != "local":
            raise ValueError("RecipeRepository only accepts local scope recipes")
        with self._conn:
            existing = self._conn.execute(
                "SELECT entity_version, created_at FROM recipes WHERE id=?",
                (recipe.id,),
            ).fetchone()
            if existing is None:
                raise ValueError(f"Recipe {recipe.id} does not exist for update")
            next_version = int(existing["entity_version"]) + 1
            self._conn.execute(
                """
                UPDATE recipes SET
                  schema_version=?, bundled_content_version=?, bundle_export_eligible=?, export_bundle_recipe_id=?, export_bundle_recipe_version=?,
                  origin_bundled_recipe_id=?, origin_bundled_recipe_version=?, is_forked_from_bundled=?, imported_from_package_id=?, imported_from_recipe_id=?, imported_at=?, import_source_label=?, title=?, subtitle=?, author=?,
                  source_name=?, source_url=?, tags_json=?, category=?, difficulty=?, servings=?, prep_minutes=?,
                  cook_minutes=?, total_minutes=?, notes=?, cover_media_id=?, display_settings_json=?, status=?,
                  entity_version=?, updated_at=?, deleted_at=?
                WHERE id=?
                """,
                (
                    recipe.schema_version,
                    recipe.bundled_content_version,
                    int(recipe.bundle_export_eligible),
                    recipe.export_bundle_recipe_id,
                    recipe.export_bundle_recipe_version,
                    recipe.origin_bundled_recipe_id,
                    recipe.origin_bundled_recipe_version,
                    int(recipe.is_forked_from_bundled),
                    recipe.imported_from_package_id,
                    recipe.imported_from_recipe_id,
                    recipe.imported_at,
                    recipe.import_source_label,
                    recipe.title,
                    recipe.subtitle,
                    recipe.author,
                    recipe.source_name,
                    recipe.source_url,
                    json.dumps(recipe.tags),
                    recipe.category,
                    recipe.difficulty,
                    recipe.servings,
                    recipe.prep_minutes,
                    recipe.cook_minutes,
                    recipe.total_minutes,
                    recipe.notes,
                    recipe.cover_media_id,
                    json.dumps(recipe.display_settings),
                    recipe.status,
                    next_version,
                    recipe.updated_at,
                    recipe.deleted_at,
                    recipe.id,
                ),
            )
            self._replace_children(recipe, for_update=True)
            self._sync_recipe_tags(recipe.id, recipe.tags, recipe.updated_at)
            self._upsert_sync_state("recipe", recipe.id, recipe.updated_at, "desktop-local", is_tombstone=recipe.deleted_at is not None)

    def get_recipe_by_id(self, recipe_id: str) -> Recipe | None:
        row = self._conn.execute(
            """
            SELECT * FROM recipes WHERE id = ?
            """,
            (recipe_id,),
        ).fetchone()
        if row is None:
            return None
        return self._assemble_recipe(row)

    def list_recipes(self, include_deleted: bool = False) -> list[Recipe]:
        where_clause = "" if include_deleted else "WHERE deleted_at IS NULL"
        rows = self._conn.execute(
            f"SELECT * FROM recipes {where_clause} ORDER BY updated_at DESC"
        ).fetchall()
        return [self._assemble_recipe(row) for row in rows]

    def upsert_recipe_user_state(
        self,
        recipe_id: str,
        *,
        is_favorite: bool | None = None,
        mark_opened: bool = False,
        mark_cooked: bool = False,
        pinned: bool | None = None,
    ) -> None:
        now = utc_now_iso()
        existing = self._conn.execute("SELECT * FROM recipe_user_state WHERE recipe_id=?", (recipe_id,)).fetchone()
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO recipe_user_state(
                  recipe_id, is_favorite, last_opened_at, last_cooked_at, open_count, cook_count, pinned,
                  entity_version, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
                """,
                (
                    recipe_id,
                    int(is_favorite or False),
                    now if mark_opened else None,
                    now if mark_cooked else None,
                    1 if mark_opened else 0,
                    1 if mark_cooked else 0,
                    int(pinned or False),
                    now,
                    now,
                ),
            )
        else:
            values = dict(existing)
            values["is_favorite"] = int(is_favorite) if is_favorite is not None else values["is_favorite"]
            values["pinned"] = int(pinned) if pinned is not None else values["pinned"]
            if mark_opened:
                values["last_opened_at"] = now
                values["open_count"] = int(values["open_count"]) + 1
            if mark_cooked:
                values["last_cooked_at"] = now
                values["cook_count"] = int(values["cook_count"]) + 1
            self._conn.execute(
                """
                UPDATE recipe_user_state
                SET is_favorite=?, last_opened_at=?, last_cooked_at=?, open_count=?, cook_count=?, pinned=?,
                    updated_at=?, entity_version=entity_version+1, deleted_at=NULL
                WHERE recipe_id=?
                """,
                (
                    values["is_favorite"],
                    values["last_opened_at"],
                    values["last_cooked_at"],
                    values["open_count"],
                    values["cook_count"],
                    values["pinned"],
                    now,
                    recipe_id,
                ),
            )
        self._upsert_sync_state("recipe_user_state", recipe_id, now, "desktop-local", is_tombstone=False)
        self._conn.commit()

    def get_recipe_user_state(self, recipe_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM recipe_user_state WHERE recipe_id=? AND deleted_at IS NULL",
            (recipe_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_favorite_recipe_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT recipe_id FROM recipe_user_state WHERE is_favorite=1 AND deleted_at IS NULL ORDER BY updated_at DESC"
        ).fetchall()
        return [row["recipe_id"] for row in rows]

    def list_recently_opened_recipe_ids(self, limit: int = 20) -> list[str]:
        rows = self._conn.execute(
            "SELECT recipe_id FROM recipe_user_state WHERE last_opened_at IS NOT NULL AND deleted_at IS NULL ORDER BY last_opened_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row["recipe_id"] for row in rows]

    def list_recently_cooked_recipe_ids(self, limit: int = 20) -> list[str]:
        rows = self._conn.execute(
            "SELECT recipe_id FROM recipe_user_state WHERE last_cooked_at IS NOT NULL AND deleted_at IS NULL ORDER BY last_cooked_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row["recipe_id"] for row in rows]

    def list_recipes_by_ids(self, recipe_ids: list[str]) -> list[Recipe]:
        if not recipe_ids:
            return []
        placeholders = ",".join(["?"] * len(recipe_ids))
        rows = self._conn.execute(
            f"SELECT * FROM recipes WHERE id IN ({placeholders}) AND deleted_at IS NULL",
            tuple(recipe_ids),
        ).fetchall()
        recipes = [self._assemble_recipe(row) for row in rows]
        return sorted(recipes, key=lambda item: recipe_ids.index(item.id))

    def create_collection(self, name: str) -> str:
        now = utc_now_iso()
        collection_id = str(uuid4())
        self._conn.execute(
            "INSERT INTO collections(id, name, created_at, updated_at, entity_version, deleted_at) VALUES (?, ?, ?, ?, 1, NULL)",
            (collection_id, name.strip(), now, now),
        )
        self._conn.commit()
        return collection_id

    def rename_collection(self, collection_id: str, name: str) -> None:
        self._conn.execute(
            "UPDATE collections SET name=?, updated_at=?, entity_version=entity_version+1 WHERE id=? AND deleted_at IS NULL",
            (name.strip(), utc_now_iso(), collection_id),
        )
        self._conn.commit()

    def delete_collection(self, collection_id: str) -> None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE collections SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (now, now, collection_id),
        )
        self._conn.execute(
            "UPDATE collection_items SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE collection_id=?",
            (now, now, collection_id),
        )
        self._conn.commit()

    def list_collections(self) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT c.id, c.name, c.created_at, c.updated_at,
              (SELECT COUNT(*) FROM collection_items ci WHERE ci.collection_id=c.id AND ci.deleted_at IS NULL) AS recipe_count
            FROM collections c
            WHERE c.deleted_at IS NULL
            ORDER BY c.name COLLATE NOCASE ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def add_recipe_to_collection(self, collection_id: str, recipe_id: str) -> None:
        now = utc_now_iso()
        existing = self._conn.execute(
            "SELECT id FROM collection_items WHERE collection_id=? AND recipe_id=?",
            (collection_id, recipe_id),
        ).fetchone()
        if existing:
            self._conn.execute(
                "UPDATE collection_items SET deleted_at=NULL, updated_at=?, entity_version=entity_version+1 WHERE id=?",
                (now, existing["id"]),
            )
        else:
            self._conn.execute(
                "INSERT INTO collection_items(id, collection_id, recipe_id, created_at, updated_at, entity_version, deleted_at) VALUES (?, ?, ?, ?, ?, 1, NULL)",
                (str(uuid4()), collection_id, recipe_id, now, now),
            )
        self._conn.commit()

    def remove_recipe_from_collection(self, collection_id: str, recipe_id: str) -> None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE collection_items SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE collection_id=? AND recipe_id=?",
            (now, now, collection_id, recipe_id),
        )
        self._conn.commit()

    def list_collection_recipe_ids(self, collection_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT recipe_id FROM collection_items WHERE collection_id=? AND deleted_at IS NULL ORDER BY created_at DESC",
            (collection_id,),
        ).fetchall()
        return [row["recipe_id"] for row in rows]

    def add_to_working_set(self, recipe_id: str) -> None:
        now = utc_now_iso()
        existing = self._conn.execute(
            "SELECT id FROM working_set_items WHERE recipe_id=?",
            (recipe_id,),
        ).fetchone()
        if existing:
            self._conn.execute(
                "UPDATE working_set_items SET deleted_at=NULL WHERE id=?",
                (existing["id"],),
            )
        else:
            self._conn.execute(
                "INSERT INTO working_set_items(id, recipe_id, created_at, deleted_at) VALUES (?, ?, ?, NULL)",
                (str(uuid4()), recipe_id, now),
            )
        self._conn.commit()

    def remove_from_working_set(self, recipe_id: str) -> None:
        self._conn.execute(
            "UPDATE working_set_items SET deleted_at=? WHERE recipe_id=?",
            (utc_now_iso(), recipe_id),
        )
        self._conn.commit()

    def list_working_set_recipe_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT recipe_id FROM working_set_items WHERE deleted_at IS NULL ORDER BY created_at DESC"
        ).fetchall()
        return [row["recipe_id"] for row in rows]

    def create_meal_plan(self, name: str, start_date: str | None = None, end_date: str | None = None) -> str:
        now = utc_now_iso()
        meal_plan_id = str(uuid4())
        self._conn.execute(
            """
            INSERT INTO meal_plans(id, name, start_date, end_date, notes, entity_version, created_at, updated_at, deleted_at)
            VALUES (?, ?, ?, ?, NULL, 1, ?, ?, NULL)
            """,
            (meal_plan_id, name.strip(), start_date, end_date, now, now),
        )
        self._conn.commit()
        return meal_plan_id

    def list_meal_plans(self) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT mp.id, mp.name, mp.start_date, mp.end_date, mp.created_at, mp.updated_at,
              (SELECT COUNT(*) FROM meal_plan_items mpi WHERE mpi.meal_plan_id=mp.id AND mpi.deleted_at IS NULL) AS item_count
            FROM meal_plans mp
            WHERE mp.deleted_at IS NULL
            ORDER BY mp.updated_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def add_meal_plan_item(
        self,
        meal_plan_id: str,
        recipe_id: str,
        servings_override: float | None = None,
        notes: str | None = None,
        planned_date: str | None = None,
        meal_slot: str | None = None,
        slot_label: str | None = None,
        sort_order: int = 0,
    ) -> str:
        now = utc_now_iso()
        item_id = str(uuid4())
        self._conn.execute(
            """
            INSERT INTO meal_plan_items(
              id, meal_plan_id, recipe_id, servings_override, notes, planned_date, meal_slot, slot_label, sort_order,
              entity_version, created_at, updated_at, deleted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
            """,
            (item_id, meal_plan_id, recipe_id, servings_override, notes, planned_date, meal_slot, slot_label, sort_order, now, now),
        )
        self._conn.execute(
            "UPDATE meal_plans SET updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (now, meal_plan_id),
        )
        self._conn.commit()
        return item_id

    def remove_meal_plan_item(self, meal_plan_item_id: str) -> None:
        now = utc_now_iso()
        row = self._conn.execute("SELECT meal_plan_id FROM meal_plan_items WHERE id=?", (meal_plan_item_id,)).fetchone()
        self._conn.execute(
            "UPDATE meal_plan_items SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (now, now, meal_plan_item_id),
        )
        if row:
            self._conn.execute(
                "UPDATE meal_plans SET updated_at=?, entity_version=entity_version+1 WHERE id=?",
                (now, row["meal_plan_id"]),
            )
        self._conn.commit()

    def delete_meal_plan(self, meal_plan_id: str) -> None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE meal_plans SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (now, now, meal_plan_id),
        )
        self._conn.execute(
            "UPDATE meal_plan_items SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE meal_plan_id=?",
            (now, now, meal_plan_id),
        )
        self._conn.commit()

    def restore_meal_plan(self, meal_plan_id: str) -> None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE meal_plans SET deleted_at=NULL, updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (now, meal_plan_id),
        )
        self._conn.execute(
            "UPDATE meal_plan_items SET deleted_at=NULL, updated_at=?, entity_version=entity_version+1 WHERE meal_plan_id=?",
            (now, meal_plan_id),
        )
        self._conn.commit()

    def list_meal_plan_items(self, meal_plan_id: str) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT id, meal_plan_id, recipe_id, servings_override, notes, planned_date, meal_slot, slot_label, sort_order, created_at, updated_at
            FROM meal_plan_items
            WHERE meal_plan_id=? AND deleted_at IS NULL
            ORDER BY planned_date ASC, meal_slot ASC, sort_order ASC, created_at ASC
            """,
            (meal_plan_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_meal_plan_item_schedule(
        self,
        meal_plan_item_id: str,
        *,
        planned_date: str | None,
        meal_slot: str | None,
        slot_label: str | None,
        sort_order: int | None = None,
    ) -> None:
        now = utc_now_iso()
        updates = [
            "planned_date=?",
            "meal_slot=?",
            "slot_label=?",
            "updated_at=?",
            "entity_version=entity_version+1",
        ]
        args: list[object] = [planned_date, meal_slot, slot_label, now]
        if sort_order is not None:
            updates.insert(3, "sort_order=?")
            args.insert(3, sort_order)
        args.append(meal_plan_item_id)
        self._conn.execute(
            f"UPDATE meal_plan_items SET {', '.join(updates)} WHERE id=?",
            tuple(args),
        )
        self._conn.commit()

    def create_grocery_list(self, meal_plan_id: str | None, name: str) -> str:
        now = utc_now_iso()
        list_id = str(uuid4())
        self._conn.execute(
            """
            INSERT INTO grocery_lists(id, meal_plan_id, name, generated_at, entity_version, created_at, updated_at, deleted_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, NULL)
            """,
            (list_id, meal_plan_id, name, now, now, now),
        )
        self._conn.commit()
        return list_id

    def replace_grocery_list_items(self, grocery_list_id: str, items: list[dict]) -> None:
        now = utc_now_iso()
        self._conn.execute("DELETE FROM grocery_list_items WHERE grocery_list_id=?", (grocery_list_id,))
        for idx, item in enumerate(items):
            self._conn.execute(
                """
                INSERT INTO grocery_list_items(
                  id, grocery_list_id, name, quantity_value, unit, checked, source_recipe_ids_json,
                  source_type, generated_group_key, was_user_modified, sort_order,
                  entity_version, created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
                """,
                (
                    str(uuid4()),
                    grocery_list_id,
                    item["name"],
                    item.get("quantity_value"),
                    item.get("unit"),
                    int(item.get("checked", False)),
                    json.dumps(item.get("source_recipe_ids", [])),
                    item.get("source_type", "generated"),
                    item.get("generated_group_key"),
                    int(item.get("was_user_modified", False)),
                    int(item.get("sort_order", idx)),
                    now,
                    now,
                ),
            )
        self._conn.execute(
            "UPDATE grocery_lists SET updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (now, grocery_list_id),
        )
        self._conn.commit()

    def list_grocery_lists(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, meal_plan_id, name, generated_at, updated_at FROM grocery_lists WHERE deleted_at IS NULL ORDER BY generated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def list_grocery_list_items(self, grocery_list_id: str) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT id, name, quantity_value, unit, checked, source_recipe_ids_json, source_type, generated_group_key, was_user_modified, sort_order
            FROM grocery_list_items
            WHERE grocery_list_id=? AND deleted_at IS NULL
            ORDER BY sort_order ASC, name COLLATE NOCASE ASC
            """,
            (grocery_list_id,),
        ).fetchall()
        result: list[dict] = []
        for row in rows:
            payload = dict(row)
            payload["checked"] = bool(payload["checked"])
            payload["source_recipe_ids"] = json.loads(payload["source_recipe_ids_json"])
            payload["was_user_modified"] = bool(payload["was_user_modified"])
            result.append(payload)
        return result

    def toggle_grocery_item_checked(self, grocery_item_id: str, checked: bool) -> None:
        self._conn.execute(
            "UPDATE grocery_list_items SET checked=?, was_user_modified=1, updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (int(checked), utc_now_iso(), grocery_item_id),
        )
        self._conn.commit()

    def add_manual_grocery_item(
        self,
        grocery_list_id: str,
        name: str,
        quantity_value: float | None = None,
        unit: str | None = None,
    ) -> str:
        now = utc_now_iso()
        item_id = str(uuid4())
        max_row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) AS max_sort FROM grocery_list_items WHERE grocery_list_id=? AND deleted_at IS NULL",
            (grocery_list_id,),
        ).fetchone()
        sort_order = int(max_row["max_sort"]) + 1
        self._conn.execute(
            """
            INSERT INTO grocery_list_items(
              id, grocery_list_id, name, quantity_value, unit, checked, source_recipe_ids_json,
              source_type, generated_group_key, was_user_modified, sort_order,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, 0, '[]', 'manual', NULL, 1, ?, 1, ?, ?, NULL)
            """,
            (item_id, grocery_list_id, name.strip(), quantity_value, unit, sort_order, now, now),
        )
        self._conn.commit()
        return item_id

    def upsert_media_asset(
        self,
        *,
        id: str,
        owner_type: str,
        owner_id: str,
        file_name: str,
        mime_type: str,
        relative_path: str,
        width: int | None = None,
        height: int | None = None,
        updated_at: str | None = None,
    ) -> None:
        now = updated_at or utc_now_iso()
        self._conn.execute(
            """
            INSERT INTO media_assets(
              id, owner_type, owner_id, file_name, mime_type, relative_path, local_path, bundled_path, width, height, checksum_sha256,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              owner_type=excluded.owner_type,
              owner_id=excluded.owner_id,
              file_name=excluded.file_name,
              mime_type=excluded.mime_type,
              relative_path=excluded.relative_path,
              local_path=excluded.local_path,
              width=excluded.width,
              height=excluded.height,
              updated_at=excluded.updated_at,
              entity_version=media_assets.entity_version+1,
              deleted_at=NULL
            """,
            (id, owner_type, owner_id, file_name, mime_type, relative_path, relative_path, width, height, now, now),
        )
        self._upsert_sync_state("media_asset", id, now, "desktop-local", is_tombstone=False)
        self._conn.commit()

    def delete_media_asset(self, media_asset_id: str) -> None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE media_assets SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (now, now, media_asset_id),
        )
        self._upsert_sync_state("media_asset", media_asset_id, now, "desktop-local", is_tombstone=True)
        self._conn.commit()

    def get_media_asset(self, media_asset_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM media_assets WHERE id=? AND deleted_at IS NULL",
            (media_asset_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_media_assets(self, include_deleted: bool = False) -> list[dict]:
        if include_deleted:
            rows = self._conn.execute("SELECT * FROM media_assets ORDER BY updated_at DESC").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM media_assets WHERE deleted_at IS NULL ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def update_grocery_item(
        self,
        grocery_item_id: str,
        *,
        name: str,
        quantity_value: float | None,
        unit: str | None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE grocery_list_items
            SET name=?, quantity_value=?, unit=?, was_user_modified=1, updated_at=?, entity_version=entity_version+1
            WHERE id=?
            """,
            (name.strip(), quantity_value, unit, utc_now_iso(), grocery_item_id),
        )
        self._conn.commit()

    def delete_grocery_item(self, grocery_item_id: str) -> None:
        self._conn.execute(
            "UPDATE grocery_list_items SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE id=?",
            (utc_now_iso(), utc_now_iso(), grocery_item_id),
        )
        self._conn.commit()

    def reorder_grocery_items(self, grocery_list_id: str, ordered_item_ids: list[str]) -> None:
        now = utc_now_iso()
        for idx, item_id in enumerate(ordered_item_ids):
            self._conn.execute(
                """
                UPDATE grocery_list_items
                SET sort_order=?, updated_at=?, entity_version=entity_version+1
                WHERE id=? AND grocery_list_id=? AND deleted_at IS NULL
                """,
                (idx, now, item_id, grocery_list_id),
            )
        self._conn.commit()

    def delete_recipe(self, recipe_id: str, deleted_at: str | None = None) -> None:
        deleted_at_value = deleted_at or utc_now_iso()
        row = self._conn.execute(
            "SELECT entity_version FROM recipes WHERE id=?",
            (recipe_id,),
        ).fetchone()
        if row is None:
            return
        with self._conn:
            self._conn.execute(
                "UPDATE recipes SET deleted_at=?, updated_at=?, entity_version=? WHERE id=?",
                (deleted_at_value, deleted_at_value, int(row["entity_version"]) + 1, recipe_id),
            )
            self._upsert_sync_state("recipe", recipe_id, deleted_at_value, "desktop-local", is_tombstone=True)

    def upsert_recipe(self, recipe: Recipe) -> None:
        existing = self.get_recipe_by_id(recipe.id)
        if existing is None:
            self.create_recipe(recipe)
        else:
            self.update_recipe(recipe)

    def upsert_entity_change(self, entity_type: str, body: dict, updated_at_utc: str, device_id: str) -> None:
        with self._conn:
            if entity_type == "recipe":
                recipe = Recipe.from_dict(body)
                recipe.scope = "local"
                recipe.updated_at = updated_at_utc
                self.upsert_recipe(recipe)
                return
            handlers = {
                "recipe_equipment_item": ("recipe_equipment", "recipe_id", self._upsert_equipment),
                "recipe_ingredient_item": ("recipe_ingredients", "recipe_id", self._upsert_ingredient),
                "recipe_step": ("recipe_steps", "recipe_id", self._upsert_step),
                "step_link": ("step_links", "step_id", self._upsert_link),
                "step_timer": ("step_timers", "step_id", self._upsert_timer),
                "global_equipment": ("global_equipment", "id", self._upsert_global_equipment),
                "catalog_ingredient": ("catalog_ingredient", "id", self._upsert_catalog_ingredient),
                "tag": ("tags", "id", self._upsert_tag),
                "collection": ("collections", "id", self._upsert_collection),
                "collection_item": ("collection_items", "id", self._upsert_collection_item),
                "meal_plan": ("meal_plans", "id", self._upsert_meal_plan),
                "meal_plan_item": ("meal_plan_items", "id", self._upsert_meal_plan_item),
                "grocery_list": ("grocery_lists", "id", self._upsert_grocery_list),
                "grocery_list_item": ("grocery_list_items", "id", self._upsert_grocery_list_item),
                "recipe_user_state": ("recipe_user_state", "recipe_id", self._upsert_recipe_user_state),
                "media_asset": ("media_assets", "id", self._upsert_media_asset),
            }
            if entity_type not in handlers:
                raise ValueError(f"Unsupported entity_type: {entity_type}")
            _, id_field, handler = handlers[entity_type]
            handler(body, updated_at_utc)
            self._upsert_sync_state(entity_type, body[id_field], updated_at_utc, device_id, is_tombstone=False)

    def tombstone_entity(self, entity_type: str, entity_id: str, updated_at_utc: str, device_id: str) -> None:
        with self._conn:
            table_by_type = {
                "recipe": "recipes",
                "recipe_equipment_item": "recipe_equipment",
                "recipe_ingredient_item": "recipe_ingredients",
                "recipe_step": "recipe_steps",
                "step_link": "step_links",
                "step_timer": "step_timers",
                "global_equipment": "global_equipment",
                "catalog_ingredient": "catalog_ingredient",
                "tag": "tags",
                "collection": "collections",
                "collection_item": "collection_items",
                "meal_plan": "meal_plans",
                "meal_plan_item": "meal_plan_items",
                "grocery_list": "grocery_lists",
                "grocery_list_item": "grocery_list_items",
                "recipe_user_state": "recipe_user_state",
                "media_asset": "media_assets",
            }
            table = table_by_type.get(entity_type)
            if table is None:
                raise ValueError(f"Unsupported entity_type: {entity_type}")
            key_col = "recipe_id" if entity_type == "recipe_user_state" else "id"
            self._conn.execute(
                f"UPDATE {table} SET deleted_at=?, updated_at=?, entity_version=entity_version+1 WHERE {key_col}=?",
                (updated_at_utc, updated_at_utc, entity_id),
            )
            self._upsert_sync_state(entity_type, entity_id, updated_at_utc, device_id, is_tombstone=True)

    def get_entity_metadata(self, entity_type: str, entity_id: str) -> tuple[str, int] | None:
        table_mapping = {
            "recipe": ("recipes", "id"),
            "recipe_equipment_item": ("recipe_equipment", "id"),
            "recipe_ingredient_item": ("recipe_ingredients", "id"),
            "recipe_step": ("recipe_steps", "id"),
            "step_link": ("step_links", "id"),
            "step_timer": ("step_timers", "id"),
            "global_equipment": ("global_equipment", "id"),
            "catalog_ingredient": ("catalog_ingredient", "id"),
            "tag": ("tags", "id"),
            "collection": ("collections", "id"),
            "collection_item": ("collection_items", "id"),
            "meal_plan": ("meal_plans", "id"),
            "meal_plan_item": ("meal_plan_items", "id"),
            "grocery_list": ("grocery_lists", "id"),
            "grocery_list_item": ("grocery_list_items", "id"),
            "recipe_user_state": ("recipe_user_state", "recipe_id"),
            "media_asset": ("media_assets", "id"),
        }.get(entity_type)
        if table_mapping is None:
            return None
        table, key_col = table_mapping
        row = self._conn.execute(
            f"SELECT updated_at, entity_version FROM {table} WHERE {key_col}=?",
            (entity_id,),
        ).fetchone()
        if row is None:
            return None
        return (row["updated_at"], int(row["entity_version"]))

    def list_entity_changes_since(self, since_cursor: str | None) -> list[dict]:
        queries = [
            ("recipe", "recipes", "id"),
            ("recipe_equipment_item", "recipe_equipment", "id"),
            ("recipe_ingredient_item", "recipe_ingredients", "id"),
            ("recipe_step", "recipe_steps", "id"),
            ("step_link", "step_links", "id"),
            ("step_timer", "step_timers", "id"),
            ("global_equipment", "global_equipment", "id"),
            ("catalog_ingredient", "catalog_ingredient", "id"),
            ("tag", "tags", "id"),
            ("collection", "collections", "id"),
            ("collection_item", "collection_items", "id"),
            ("meal_plan", "meal_plans", "id"),
            ("meal_plan_item", "meal_plan_items", "id"),
            ("grocery_list", "grocery_lists", "id"),
            ("grocery_list_item", "grocery_list_items", "id"),
            ("recipe_user_state", "recipe_user_state", "recipe_id"),
            ("media_asset", "media_assets", "id"),
        ]
        changes: list[dict] = []
        for entity_type, table, key_col in queries:
            rows = self._conn.execute(
                f"SELECT {key_col} AS entity_id, updated_at, deleted_at, entity_version FROM {table} WHERE (? IS NULL OR updated_at > ?)",
                (since_cursor, since_cursor),
            ).fetchall()
            for row in rows:
                body = None if row["deleted_at"] else self._load_entity_body(entity_type, row["entity_id"])
                changes.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": row["entity_id"],
                        "op": "delete" if row["deleted_at"] else "upsert",
                        "entity_version": int(row["entity_version"]),
                        "updated_at_utc": row["updated_at"],
                        "body": body,
                        "source_scope": "local",
                    }
                )
        changes.sort(key=lambda item: item["updated_at_utc"])
        return changes

    def _sync_recipe_tags(self, recipe_id: str, tag_names: list[str], updated_at_utc: str) -> None:
        """Align recipe_tags with recipe.tags; create tag rows as needed."""
        seen_lower: set[str] = set()
        ordered_unique: list[str] = []
        for raw in tag_names or []:
            if not raw or not str(raw).strip():
                continue
            name = str(raw).strip()
            key = name.lower()
            if key in seen_lower:
                continue
            seen_lower.add(key)
            ordered_unique.append(name)
        self._conn.execute("DELETE FROM recipe_tags WHERE recipe_id=?", (recipe_id,))
        for name in ordered_unique:
            row = self._conn.execute(
                "SELECT id, deleted_at FROM tags WHERE lower(name) = lower(?)",
                (name,),
            ).fetchone()
            if row is None:
                tid = str(uuid4())
                self._conn.execute(
                    """
                    INSERT INTO tags(id, name, color, entity_version, created_at, updated_at, deleted_at)
                    VALUES(?,?,NULL,1,?,?,NULL)
                    """,
                    (tid, name, updated_at_utc, updated_at_utc),
                )
                self._upsert_sync_state("tag", tid, updated_at_utc, "desktop-local", is_tombstone=False)
            else:
                tid = row["id"]
                if row["deleted_at"] is not None:
                    self._conn.execute(
                        """
                        UPDATE tags SET deleted_at=NULL, name=?, updated_at=?, entity_version=entity_version+1
                        WHERE id=?
                        """,
                        (name, updated_at_utc, tid),
                    )
                    self._upsert_sync_state("tag", tid, updated_at_utc, "desktop-local", is_tombstone=False)
            self._conn.execute(
                "INSERT OR IGNORE INTO recipe_tags(recipe_id, tag_id) VALUES(?,?)",
                (recipe_id, tid),
            )

    def list_global_equipment_for_picker(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT id, name, notes, media_id FROM global_equipment WHERE deleted_at IS NULL ORDER BY lower(name)"
        ).fetchall()

    def list_tags_for_picker(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT id, name, color FROM tags WHERE deleted_at IS NULL ORDER BY lower(name)"
        ).fetchall()

    def create_global_equipment(
        self, name: str, *, notes: str | None = None, media_id: str | None = None
    ) -> str:
        name = name.strip()
        if not name:
            raise ValueError("global equipment name cannot be empty")
        now = utc_now_iso()
        ge_id = str(uuid4())
        with self._conn:
            self._upsert_global_equipment(
                {"id": ge_id, "name": name, "notes": notes, "media_id": media_id, "created_at": now},
                now,
            )
            self._upsert_sync_state("global_equipment", ge_id, now, "desktop-local", is_tombstone=False)
        return ge_id

    def catalog_ingredient_id_to_name(self) -> dict[str, str]:
        return {
            str(row["id"]): str(row["name"])
            for row in self._conn.execute("SELECT id, name FROM catalog_ingredient WHERE deleted_at IS NULL").fetchall()
        }

    def list_catalog_ingredient_for_picker(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT id, name, notes FROM catalog_ingredient WHERE deleted_at IS NULL ORDER BY lower(name)"
        ).fetchall()

    def search_catalog_ingredients(self, query: str, *, limit: int = 20) -> list[sqlite3.Row]:
        needle = _normalize_catalog_ingredient_name(query)
        if not needle:
            return []
        like = f"%{needle}%"
        return self._conn.execute(
            """
            SELECT id, name, notes FROM catalog_ingredient
            WHERE deleted_at IS NULL AND normalized_name LIKE ?
            ORDER BY lower(name) LIMIT ?
            """,
            (like, limit),
        ).fetchall()

    def create_catalog_ingredient(self, name: str, *, notes: str | None = None) -> str:
        name = name.strip()
        if not name:
            raise ValueError("catalog ingredient name cannot be empty")
        now = utc_now_iso()
        cid = str(uuid4())
        with self._conn:
            self._upsert_catalog_ingredient(
                {
                    "id": cid,
                    "name": name,
                    "notes": notes,
                    "normalized_name": _normalize_catalog_ingredient_name(name),
                    "created_at": now,
                },
                now,
            )
            self._upsert_sync_state("catalog_ingredient", cid, now, "desktop-local", is_tombstone=False)
        return cid

    def _replace_children(self, recipe: Recipe, for_update: bool) -> None:
        if for_update:
            self._conn.execute("DELETE FROM step_timers WHERE step_id IN (SELECT id FROM recipe_steps WHERE recipe_id=?)", (recipe.id,))
            self._conn.execute("DELETE FROM step_links WHERE step_id IN (SELECT id FROM recipe_steps WHERE recipe_id=?)", (recipe.id,))
            self._conn.execute("DELETE FROM recipe_steps WHERE recipe_id=?", (recipe.id,))
            self._conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id=?", (recipe.id,))
            self._conn.execute("DELETE FROM recipe_equipment WHERE recipe_id=?", (recipe.id,))

        for item in recipe.equipment:
            self._upsert_equipment(
                {
                    "id": item.id,
                    "recipe_id": recipe.id,
                    "name": item.name,
                    "description": item.description,
                    "why_used": item.why_used,
                    "is_required": item.is_required,
                    "notes": item.notes,
                    "affiliate_url": item.affiliate_url,
                    "alternate_equipment_text": item.alternate_equipment_text,
                    "media_id": item.media_id,
                    "display_order": item.display_order,
                    "global_equipment_id": item.global_equipment_id,
                },
                recipe.updated_at,
            )
        for item in recipe.ingredients:
            self._upsert_ingredient(
                {
                    "id": item.id,
                    "recipe_id": recipe.id,
                    "raw_text": item.raw_text,
                    "quantity_value": item.quantity_value,
                    "quantity_text": item.quantity_text,
                    "unit": item.unit,
                    "ingredient_name": item.ingredient_name,
                    "preparation_notes": item.preparation_notes,
                    "substitutions": item.substitutions,
                    "affiliate_url": item.affiliate_url,
                    "recommended_product": item.recommended_product,
                    "media_id": item.media_id,
                    "is_optional": item.is_optional,
                    "display_order": item.display_order,
                    "catalog_ingredient_id": item.catalog_ingredient_id,
                    "sub_recipe_id": item.sub_recipe_id,
                    "sub_recipe_usage_type": item.sub_recipe_usage_type,
                    "sub_recipe_multiplier": item.sub_recipe_multiplier,
                    "sub_recipe_display_name": item.sub_recipe_display_name,
                },
                recipe.updated_at,
            )
        for step in recipe.steps:
            self._upsert_step(
                {
                    "id": step.id,
                    "recipe_id": recipe.id,
                    "title": step.title,
                    "body_text": step.body_text,
                    "display_order": step.display_order,
                    "step_type": step.step_type,
                    "estimated_seconds": step.estimated_seconds,
                    "media_id": step.media_id,
                },
                recipe.updated_at,
            )
            for timer in step.timers:
                self._upsert_timer(
                    {
                        "id": timer.id,
                        "step_id": step.id,
                        "label": timer.label,
                        "duration_seconds": timer.duration_seconds,
                        "auto_start": timer.auto_start,
                        "alert_sound_key": timer.alert_sound_key,
                        "alert_vibrate": timer.alert_vibrate,
                    },
                    recipe.updated_at,
                )
        for link in recipe.step_links:
            self._upsert_link(
                {
                    "id": link.id,
                    "step_id": link.step_id,
                    "target_type": link.target_type,
                    "target_id": link.target_id,
                    "token_key": link.token_key,
                    "label_snapshot": link.label_snapshot,
                    "label_override": link.label_override,
                },
                recipe.updated_at,
            )

    def _assemble_recipe(self, recipe_row: sqlite3.Row) -> Recipe:
        recipe_id = recipe_row["id"]
        equipment_rows = self._conn.execute(
            "SELECT * FROM recipe_equipment WHERE recipe_id=? AND deleted_at IS NULL ORDER BY display_order",
            (recipe_id,),
        ).fetchall()
        ingredient_rows = self._conn.execute(
            "SELECT * FROM recipe_ingredients WHERE recipe_id=? AND deleted_at IS NULL ORDER BY display_order",
            (recipe_id,),
        ).fetchall()
        step_rows = self._conn.execute(
            "SELECT * FROM recipe_steps WHERE recipe_id=? AND deleted_at IS NULL ORDER BY display_order",
            (recipe_id,),
        ).fetchall()
        link_rows = self._conn.execute(
            """
            SELECT sl.* FROM step_links sl
            JOIN recipe_steps rs ON rs.id = sl.step_id
            WHERE rs.recipe_id=? AND sl.deleted_at IS NULL
            ORDER BY sl.created_at
            """,
            (recipe_id,),
        ).fetchall()
        timers_by_step = self._load_timers_by_step([row["id"] for row in step_rows])

        return Recipe(
            id=recipe_id,
            scope="local",
            title=recipe_row["title"],
            status=recipe_row["status"],
            created_at=recipe_row["created_at"],
            updated_at=recipe_row["updated_at"],
            equipment=[
                RecipeEquipmentItem(
                    id=row["id"],
                    name=row["name"],
                    is_required=bool(row["is_required"]),
                    display_order=row["display_order"],
                    description=row["description"],
                    why_used=row["why_used"],
                    notes=row["notes"],
                    affiliate_url=row["affiliate_url"],
                    alternate_equipment_text=row["alternate_equipment_text"],
                    media_id=row["media_id"],
                    global_equipment_id=row["global_equipment_id"],
                )
                for row in equipment_rows
            ],
            ingredients=[
                RecipeIngredientItem(
                    id=row["id"],
                    raw_text=row["raw_text"],
                    is_optional=bool(row["is_optional"]),
                    display_order=row["display_order"],
                    quantity_value=row["quantity_value"],
                    quantity_text=row["quantity_text"],
                    unit=row["unit"],
                    ingredient_name=row["ingredient_name"],
                    preparation_notes=row["preparation_notes"],
                    substitutions=row["substitutions"],
                    affiliate_url=row["affiliate_url"],
                    recommended_product=row["recommended_product"],
                    media_id=row["media_id"],
                    catalog_ingredient_id=row["catalog_ingredient_id"] if row["catalog_ingredient_id"] else None,
                    sub_recipe_id=row["sub_recipe_id"] if row["sub_recipe_id"] else None,
                    sub_recipe_usage_type=row["sub_recipe_usage_type"] if row["sub_recipe_usage_type"] else None,
                    sub_recipe_multiplier=float(row["sub_recipe_multiplier"]) if row["sub_recipe_multiplier"] is not None else None,
                    sub_recipe_display_name=row["sub_recipe_display_name"] if row["sub_recipe_display_name"] else None,
                )
                for row in ingredient_rows
            ],
            steps=[
                RecipeStep(
                    id=row["id"],
                    body_text=row["body_text"],
                    display_order=row["display_order"],
                    step_type=row["step_type"],
                    timers=timers_by_step.get(row["id"], []),
                    title=row["title"],
                    estimated_seconds=row["estimated_seconds"],
                    media_id=row["media_id"],
                )
                for row in step_rows
            ],
            schema_version=recipe_row["schema_version"],
            bundled_content_version=recipe_row["bundled_content_version"],
            bundle_export_eligible=bool(recipe_row["bundle_export_eligible"]),
            export_bundle_recipe_id=recipe_row["export_bundle_recipe_id"],
            export_bundle_recipe_version=recipe_row["export_bundle_recipe_version"],
            origin_bundled_recipe_id=recipe_row["origin_bundled_recipe_id"],
            origin_bundled_recipe_version=recipe_row["origin_bundled_recipe_version"],
            is_forked_from_bundled=bool(recipe_row["is_forked_from_bundled"]),
            imported_from_package_id=recipe_row["imported_from_package_id"],
            imported_from_recipe_id=recipe_row["imported_from_recipe_id"],
            imported_at=recipe_row["imported_at"],
            import_source_label=recipe_row["import_source_label"],
            subtitle=recipe_row["subtitle"],
            author=recipe_row["author"],
            source_name=recipe_row["source_name"],
            source_url=recipe_row["source_url"],
            tags=json.loads(recipe_row["tags_json"] or "[]"),
            category=recipe_row["category"],
            difficulty=recipe_row["difficulty"],
            servings=recipe_row["servings"],
            prep_minutes=recipe_row["prep_minutes"],
            cook_minutes=recipe_row["cook_minutes"],
            total_minutes=recipe_row["total_minutes"],
            notes=recipe_row["notes"],
            cover_media_id=recipe_row["cover_media_id"],
            display_settings=json.loads(recipe_row["display_settings_json"] or "{}"),
            deleted_at=recipe_row["deleted_at"],
            step_links=[
                StepLink(
                    id=row["id"],
                    step_id=row["step_id"],
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    token_key=row["token_key"],
                    label_snapshot=row["label_snapshot"],
                    label_override=row["label_override"],
                )
                for row in link_rows
            ],
        )

    def _load_timers_by_step(self, step_ids: Sequence[str]) -> dict[str, list[StepTimer]]:
        if not step_ids:
            return {}
        placeholders = ",".join(["?"] * len(step_ids))
        rows = self._conn.execute(
            f"SELECT * FROM step_timers WHERE step_id IN ({placeholders}) AND deleted_at IS NULL ORDER BY created_at",
            tuple(step_ids),
        ).fetchall()
        timers_by_step: dict[str, list[StepTimer]] = {}
        for row in rows:
            timers_by_step.setdefault(row["step_id"], []).append(
                StepTimer(
                    id=row["id"],
                    label=row["label"],
                    duration_seconds=row["duration_seconds"],
                    auto_start=bool(row["auto_start"]),
                    alert_sound_key=row["alert_sound_key"],
                    alert_vibrate=bool(row["alert_vibrate"]),
                )
            )
        return timers_by_step

    def _upsert_equipment(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO recipe_equipment(
              id, recipe_id, name, description, why_used, is_required, notes, affiliate_url, alternate_equipment_text,
              media_id, display_order, global_equipment_id, entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              recipe_id=excluded.recipe_id, name=excluded.name, description=excluded.description, why_used=excluded.why_used,
              is_required=excluded.is_required, notes=excluded.notes, affiliate_url=excluded.affiliate_url,
              alternate_equipment_text=excluded.alternate_equipment_text, media_id=excluded.media_id,
              display_order=excluded.display_order, global_equipment_id=excluded.global_equipment_id,
              entity_version=recipe_equipment.entity_version+1, updated_at=excluded.updated_at, deleted_at=NULL
            """,
            (
                body["id"],
                body["recipe_id"],
                body["name"],
                body.get("description"),
                body.get("why_used"),
                int(body["is_required"]),
                body.get("notes"),
                body.get("affiliate_url"),
                body.get("alternate_equipment_text"),
                body.get("media_id"),
                body["display_order"],
                body.get("global_equipment_id"),
                updated_at_utc,
                updated_at_utc,
            ),
        )

    def _upsert_ingredient(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO recipe_ingredients(
              id, recipe_id, raw_text, quantity_value, quantity_text, unit, ingredient_name, preparation_notes,
              substitutions, affiliate_url, recommended_product, media_id, is_optional, display_order,
              catalog_ingredient_id,
              sub_recipe_id, sub_recipe_usage_type, sub_recipe_multiplier, sub_recipe_display_name,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              recipe_id=excluded.recipe_id, raw_text=excluded.raw_text, quantity_value=excluded.quantity_value,
              quantity_text=excluded.quantity_text, unit=excluded.unit, ingredient_name=excluded.ingredient_name,
              preparation_notes=excluded.preparation_notes, substitutions=excluded.substitutions,
              affiliate_url=excluded.affiliate_url, recommended_product=excluded.recommended_product,
              media_id=excluded.media_id, is_optional=excluded.is_optional, display_order=excluded.display_order,
              catalog_ingredient_id=excluded.catalog_ingredient_id,
              sub_recipe_id=excluded.sub_recipe_id, sub_recipe_usage_type=excluded.sub_recipe_usage_type,
              sub_recipe_multiplier=excluded.sub_recipe_multiplier, sub_recipe_display_name=excluded.sub_recipe_display_name,
              entity_version=recipe_ingredients.entity_version+1, updated_at=excluded.updated_at, deleted_at=NULL
            """,
            (
                body["id"],
                body["recipe_id"],
                body["raw_text"],
                body.get("quantity_value"),
                body.get("quantity_text"),
                body.get("unit"),
                body.get("ingredient_name"),
                body.get("preparation_notes"),
                body.get("substitutions"),
                body.get("affiliate_url"),
                body.get("recommended_product"),
                body.get("media_id"),
                int(body["is_optional"]),
                body["display_order"],
                body.get("catalog_ingredient_id"),
                body.get("sub_recipe_id"),
                body.get("sub_recipe_usage_type"),
                body.get("sub_recipe_multiplier"),
                body.get("sub_recipe_display_name"),
                updated_at_utc,
                updated_at_utc,
            ),
        )

    def _upsert_step(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO recipe_steps(
              id, recipe_id, title, body_text, display_order, step_type, estimated_seconds, media_id,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              recipe_id=excluded.recipe_id, title=excluded.title, body_text=excluded.body_text,
              display_order=excluded.display_order, step_type=excluded.step_type, estimated_seconds=excluded.estimated_seconds,
              media_id=excluded.media_id, entity_version=recipe_steps.entity_version+1, updated_at=excluded.updated_at, deleted_at=NULL
            """,
            (
                body["id"],
                body["recipe_id"],
                body.get("title"),
                body["body_text"],
                body["display_order"],
                body["step_type"],
                body.get("estimated_seconds"),
                body.get("media_id"),
                updated_at_utc,
                updated_at_utc,
            ),
        )

    def _upsert_link(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO step_links(
              id, step_id, target_type, target_id, token_key, label_snapshot, label_override,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              step_id=excluded.step_id, target_type=excluded.target_type, target_id=excluded.target_id,
              token_key=excluded.token_key, label_snapshot=excluded.label_snapshot, label_override=excluded.label_override,
              entity_version=step_links.entity_version+1, updated_at=excluded.updated_at, deleted_at=NULL
            """,
            (
                body["id"],
                body["step_id"],
                body["target_type"],
                body["target_id"],
                body["token_key"],
                body["label_snapshot"],
                body.get("label_override"),
                updated_at_utc,
                updated_at_utc,
            ),
        )

    def _upsert_timer(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO step_timers(
              id, step_id, label, duration_seconds, auto_start, alert_sound_key, alert_vibrate,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              step_id=excluded.step_id, label=excluded.label, duration_seconds=excluded.duration_seconds,
              auto_start=excluded.auto_start, alert_sound_key=excluded.alert_sound_key,
              alert_vibrate=excluded.alert_vibrate,
              entity_version=step_timers.entity_version+1, updated_at=excluded.updated_at, deleted_at=NULL
            """,
            (
                body["id"],
                body["step_id"],
                body["label"],
                body["duration_seconds"],
                int(body["auto_start"]),
                body.get("alert_sound_key"),
                int(body.get("alert_vibrate", False)),
                updated_at_utc,
                updated_at_utc,
            ),
        )

    def _upsert_global_equipment(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO global_equipment(
              id, name, notes, media_id, entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name,
              notes=excluded.notes,
              media_id=excluded.media_id,
              entity_version=global_equipment.entity_version+1,
              updated_at=excluded.updated_at,
              deleted_at=NULL
            """,
            (
                body["id"],
                body["name"],
                body.get("notes"),
                body.get("media_id"),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _upsert_catalog_ingredient(self, body: dict, updated_at_utc: str) -> None:
        name = body["name"]
        normalized = body.get("normalized_name") or _normalize_catalog_ingredient_name(name)
        self._conn.execute(
            """
            INSERT INTO catalog_ingredient(
              id, name, normalized_name, notes, entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name,
              normalized_name=excluded.normalized_name,
              notes=excluded.notes,
              entity_version=catalog_ingredient.entity_version+1,
              updated_at=excluded.updated_at,
              deleted_at=NULL
            """,
            (
                body["id"],
                name,
                normalized,
                body.get("notes"),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _upsert_tag(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO tags(id, name, color, entity_version, created_at, updated_at, deleted_at)
            VALUES (?, ?, ?, 1, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name,
              color=excluded.color,
              entity_version=tags.entity_version+1,
              updated_at=excluded.updated_at,
              deleted_at=NULL
            """,
            (
                body["id"],
                body["name"],
                body.get("color"),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _upsert_collection(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO collections(id, name, created_at, updated_at, entity_version, deleted_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name,
              updated_at=excluded.updated_at,
              entity_version=excluded.entity_version,
              deleted_at=NULL
            """,
            (
                body["id"],
                body["name"],
                body.get("created_at", updated_at_utc),
                updated_at_utc,
                int(body.get("entity_version", 1)),
            ),
        )

    def _upsert_collection_item(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO collection_items(id, collection_id, recipe_id, created_at, updated_at, entity_version, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              collection_id=excluded.collection_id,
              recipe_id=excluded.recipe_id,
              updated_at=excluded.updated_at,
              entity_version=excluded.entity_version,
              deleted_at=NULL
            """,
            (
                body["id"],
                body["collection_id"],
                body["recipe_id"],
                body.get("created_at", updated_at_utc),
                updated_at_utc,
                int(body.get("entity_version", 1)),
            ),
        )

    def _upsert_meal_plan(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO meal_plans(id, name, start_date, end_date, notes, entity_version, created_at, updated_at, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name,
              start_date=excluded.start_date,
              end_date=excluded.end_date,
              notes=excluded.notes,
              updated_at=excluded.updated_at,
              entity_version=excluded.entity_version,
              deleted_at=NULL
            """,
            (
                body["id"],
                body["name"],
                body.get("start_date"),
                body.get("end_date"),
                body.get("notes"),
                int(body.get("entity_version", 1)),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _upsert_meal_plan_item(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO meal_plan_items(
              id, meal_plan_id, recipe_id, servings_override, notes, planned_date, meal_slot, slot_label, sort_order,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              meal_plan_id=excluded.meal_plan_id,
              recipe_id=excluded.recipe_id,
              servings_override=excluded.servings_override,
              notes=excluded.notes,
              planned_date=excluded.planned_date,
              meal_slot=excluded.meal_slot,
              slot_label=excluded.slot_label,
              sort_order=excluded.sort_order,
              updated_at=excluded.updated_at,
              entity_version=excluded.entity_version,
              deleted_at=NULL
            """,
            (
                body["id"],
                body["meal_plan_id"],
                body["recipe_id"],
                body.get("servings_override"),
                body.get("notes"),
                body.get("planned_date"),
                body.get("meal_slot"),
                body.get("slot_label"),
                int(body.get("sort_order", 0)),
                int(body.get("entity_version", 1)),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _upsert_grocery_list(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO grocery_lists(
              id, meal_plan_id, name, generated_at, entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              meal_plan_id=excluded.meal_plan_id,
              name=excluded.name,
              generated_at=excluded.generated_at,
              updated_at=excluded.updated_at,
              entity_version=excluded.entity_version,
              deleted_at=NULL
            """,
            (
                body["id"],
                body.get("meal_plan_id"),
                body["name"],
                body.get("generated_at", updated_at_utc),
                int(body.get("entity_version", 1)),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _upsert_grocery_list_item(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO grocery_list_items(
              id, grocery_list_id, name, quantity_value, unit, checked, source_recipe_ids_json,
              source_type, generated_group_key, was_user_modified, sort_order,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              grocery_list_id=excluded.grocery_list_id,
              name=excluded.name,
              quantity_value=excluded.quantity_value,
              unit=excluded.unit,
              checked=excluded.checked,
              source_recipe_ids_json=excluded.source_recipe_ids_json,
              source_type=excluded.source_type,
              generated_group_key=excluded.generated_group_key,
              was_user_modified=excluded.was_user_modified,
              sort_order=excluded.sort_order,
              updated_at=excluded.updated_at,
              entity_version=excluded.entity_version,
              deleted_at=NULL
            """,
            (
                body["id"],
                body["grocery_list_id"],
                body["name"],
                body.get("quantity_value"),
                body.get("unit"),
                int(body.get("checked", False)),
                json.dumps(body.get("source_recipe_ids", [])),
                body.get("source_type", "generated"),
                body.get("generated_group_key"),
                int(body.get("was_user_modified", False)),
                int(body.get("sort_order", 0)),
                int(body.get("entity_version", 1)),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _upsert_recipe_user_state(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO recipe_user_state(
              recipe_id, is_favorite, last_opened_at, last_cooked_at, open_count, cook_count, pinned,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(recipe_id) DO UPDATE SET
              is_favorite=excluded.is_favorite,
              last_opened_at=excluded.last_opened_at,
              last_cooked_at=excluded.last_cooked_at,
              open_count=excluded.open_count,
              cook_count=excluded.cook_count,
              pinned=excluded.pinned,
              updated_at=excluded.updated_at,
              entity_version=excluded.entity_version,
              deleted_at=NULL
            """,
            (
                body["recipe_id"],
                int(body.get("is_favorite", False)),
                body.get("last_opened_at"),
                body.get("last_cooked_at"),
                int(body.get("open_count", 0)),
                int(body.get("cook_count", 0)),
                int(body.get("pinned", False)),
                int(body.get("entity_version", 1)),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _upsert_media_asset(self, body: dict, updated_at_utc: str) -> None:
        self._conn.execute(
            """
            INSERT INTO media_assets(
              id, owner_type, owner_id, file_name, mime_type, relative_path, local_path, bundled_path, width, height, checksum_sha256,
              entity_version, created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET
              owner_type=excluded.owner_type,
              owner_id=excluded.owner_id,
              file_name=excluded.file_name,
              mime_type=excluded.mime_type,
              relative_path=excluded.relative_path,
              local_path=excluded.local_path,
              bundled_path=excluded.bundled_path,
              width=excluded.width,
              height=excluded.height,
              checksum_sha256=excluded.checksum_sha256,
              updated_at=excluded.updated_at,
              entity_version=excluded.entity_version,
              deleted_at=NULL
            """,
            (
                body["id"],
                body["owner_type"],
                body["owner_id"],
                body.get("file_name"),
                body["mime_type"],
                body.get("relative_path"),
                body.get("local_path"),
                body.get("bundled_path"),
                body.get("width"),
                body.get("height"),
                body.get("checksum_sha256"),
                int(body.get("entity_version", 1)),
                body.get("created_at", updated_at_utc),
                updated_at_utc,
            ),
        )

    def _load_entity_body(self, entity_type: str, entity_id: str) -> dict | None:
        if entity_type == "recipe":
            recipe = self.get_recipe_by_id(entity_id)
            return recipe.to_dict() if recipe else None
        mapping = {
            "recipe_equipment_item": ("recipe_equipment",),
            "recipe_ingredient_item": ("recipe_ingredients",),
            "recipe_step": ("recipe_steps",),
            "step_link": ("step_links",),
            "step_timer": ("step_timers",),
            "global_equipment": ("global_equipment",),
            "catalog_ingredient": ("catalog_ingredient",),
            "tag": ("tags",),
            "collection": ("collections",),
            "collection_item": ("collection_items",),
            "meal_plan": ("meal_plans",),
            "meal_plan_item": ("meal_plan_items",),
            "grocery_list": ("grocery_lists",),
            "grocery_list_item": ("grocery_list_items",),
            "recipe_user_state": ("recipe_user_state",),
            "media_asset": ("media_assets",),
        }
        if entity_type not in mapping:
            return None
        table = mapping[entity_type][0]
        key_col = "recipe_id" if entity_type == "recipe_user_state" else "id"
        row = self._conn.execute(f"SELECT * FROM {table} WHERE {key_col}=?", (entity_id,)).fetchone()
        return dict(row) if row else None

    def _upsert_sync_state(
        self, entity_type: str, entity_id: str, entity_updated_at: str, device_id: str, is_tombstone: bool
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO sync_state(entity_type, entity_id, entity_updated_at, last_modified_device_id, last_synced_at, sync_version, is_tombstone)
            VALUES(?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
              entity_updated_at=excluded.entity_updated_at,
              last_modified_device_id=excluded.last_modified_device_id,
              last_synced_at=excluded.last_synced_at,
              sync_version=sync_state.sync_version+1,
              is_tombstone=excluded.is_tombstone
            """,
            (entity_type, entity_id, entity_updated_at, device_id, utc_now_iso(), int(is_tombstone)),
        )

