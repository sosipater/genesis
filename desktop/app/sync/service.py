"""Sync service with explicit non-destructive conflict handling."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from desktop.app.domain.models import utc_now_iso
from desktop.app.persistence.recipe_repository import RecipeRepository


class SyncService:
    def __init__(self, conn: sqlite3.Connection, protocol_version: int):
        self._conn = conn
        self._repo = RecipeRepository(conn)
        self._protocol_version = protocol_version
        self._logger = logging.getLogger("recipe_forge.sync")

    def status(self) -> dict[str, Any]:
        queued = self._conn.execute(
            "SELECT COUNT(*) AS count FROM sync_state WHERE last_synced_at IS NULL"
        ).fetchone()["count"]
        last_event = self._conn.execute(
            "SELECT created_at FROM sync_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {
            "sync_protocol_version": self._protocol_version,
            "queued_changes": queued,
            "last_sync_event_at": last_event["created_at"] if last_event else None,
        }

    def handle_push(self, envelope: dict[str, Any]) -> dict[str, Any]:
        request_id = envelope["request_id"]
        session_id = envelope["session_id"]
        device_id = envelope["device_id"]
        changes = envelope["payload"]["changes"]
        results: list[dict[str, Any]] = []

        for change in changes:
            result = self._apply_change(change, device_id=device_id, request_id=request_id)
            results.append(result)

        summary = {"results": results}
        self._record_sync_event(request_id, session_id, device_id, "push", "ok", summary)
        return {
            "sync_protocol_version": self._protocol_version,
            "request_id": request_id,
            "session_id": session_id,
            "device_id": "desktop-host",
            "sent_at_utc": utc_now_iso(),
            "payload": {"results": results, "next_cursor": utc_now_iso(), "changes": []},
            "errors": [],
        }

    def handle_pull(self, envelope: dict[str, Any]) -> dict[str, Any]:
        request_id = envelope["request_id"]
        session_id = envelope["session_id"]
        device_id = envelope["device_id"]
        since_cursor = envelope["payload"].get("since_cursor")
        changes = self._repo.list_entity_changes_since(since_cursor)

        summary = {"returned_changes": len(changes)}
        self._record_sync_event(request_id, session_id, device_id, "pull", "ok", summary)
        return {
            "sync_protocol_version": self._protocol_version,
            "request_id": request_id,
            "session_id": session_id,
            "device_id": "desktop-host",
            "sent_at_utc": utc_now_iso(),
            "payload": {
                "since_cursor": since_cursor,
                "next_cursor": utc_now_iso(),
                "changes": changes,
            },
            "errors": [],
        }

    def _apply_change(self, change: dict[str, Any], device_id: str, request_id: str) -> dict[str, Any]:
        if change["source_scope"] != "local":
            return {"entity_id": change["entity_id"], "status": "rejected", "reason": "scope_not_allowed"}
        entity_type = change["entity_type"]
        if entity_type not in {
            "recipe",
            "recipe_equipment_item",
            "recipe_ingredient_item",
            "recipe_step",
            "step_link",
            "step_timer",
            "global_equipment",
            "tag",
            "collection",
            "collection_item",
            "meal_plan",
            "meal_plan_item",
            "grocery_list",
            "grocery_list_item",
            "recipe_user_state",
            "media_asset",
        }:
            return {"entity_id": change["entity_id"], "status": "rejected", "reason": "unsupported_entity_type"}

        existing = self._repo.get_entity_metadata(entity_type, change["entity_id"])
        incoming_updated_at = change["updated_at_utc"]
        incoming_entity_version = int(change.get("entity_version", 1))
        if existing and incoming_updated_at < existing[0]:
            self._record_conflict(
                request_id=request_id,
                entity_type=entity_type,
                entity_id=change["entity_id"],
                incoming_updated_at=incoming_updated_at,
                local_updated_at=existing[0],
                incoming_device_id=device_id,
                incoming_entity_version=incoming_entity_version,
                local_entity_version=existing[1],
                resolution="rejected_stale_update",
            )
            return {"entity_id": change["entity_id"], "status": "conflict", "resolution": "rejected_stale_update"}

        if change["op"] == "delete":
            self._repo.tombstone_entity(entity_type, change["entity_id"], incoming_updated_at, device_id)
            return {"entity_id": change["entity_id"], "entity_type": entity_type, "status": "applied", "op": "delete"}

        self._repo.upsert_entity_change(entity_type, change["body"], incoming_updated_at, device_id)
        return {"entity_id": change["entity_id"], "entity_type": entity_type, "status": "applied", "op": "upsert"}

    def _record_conflict(
        self,
        request_id: str,
        entity_type: str,
        entity_id: str,
        incoming_updated_at: str,
        local_updated_at: str,
        incoming_device_id: str,
        incoming_entity_version: int,
        local_entity_version: int,
        resolution: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO sync_conflicts(
              request_id, entity_type, entity_id, incoming_updated_at, local_updated_at,
              incoming_device_id, incoming_entity_version, local_entity_version, resolution, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                entity_type,
                entity_id,
                incoming_updated_at,
                local_updated_at,
                incoming_device_id,
                incoming_entity_version,
                local_entity_version,
                resolution,
                utc_now_iso(),
            ),
        )
        self._conn.commit()
        self._logger.warning(
            "Sync conflict detected",
            extra={
                "subsystem": "sync",
                "request_id": request_id,
                "device_id": incoming_device_id,
                "correlation_id": request_id,
            },
        )

    def _record_sync_event(
        self,
        request_id: str,
        session_id: str,
        device_id: str,
        direction: str,
        status: str,
        summary: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO sync_events(request_id, session_id, device_id, direction, status, summary_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (request_id, session_id, device_id, direction, status, json.dumps(summary), utc_now_iso()),
        )
        self._conn.commit()

