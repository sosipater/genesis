import json
from pathlib import Path

from fastapi.testclient import TestClient

from desktop.app.sync.api import create_app


def test_sync_push_and_pull_contract(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    app = create_app(root=root, db_path=tmp_path / "sync.db")
    client = TestClient(app)

    envelope = json.loads((root / "shared" / "samples" / "sample_sync_envelope.json").read_text(encoding="utf-8"))
    sample_recipe = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    envelope["payload"]["changes"][0]["body"] = sample_recipe

    push_response = client.post("/sync/push", json=envelope)
    assert push_response.status_code == 200
    push_payload = push_response.json()
    assert push_payload["payload"]["results"][0]["status"] == "applied"

    pull_request = {
        "sync_protocol_version": 1,
        "request_id": "123e4567-e89b-12d3-a456-426614174101",
        "session_id": "desktop-mobile-session-1",
        "device_id": "android-pixel-01",
        "sent_at_utc": "2026-04-15T00:00:10Z",
        "payload": {"since_cursor": None, "next_cursor": None, "changes": []},
        "errors": [],
    }
    pull_response = client.post("/sync/pull", json=pull_request)
    assert pull_response.status_code == 200
    changes = pull_response.json()["payload"]["changes"]
    assert any(change["entity_type"] == "recipe" for change in changes)
    assert any(change["entity_type"] == "recipe_step" for change in changes)
    assert any(change["entity_type"] == "step_timer" for change in changes)


def test_sync_conflict_detects_stale_update(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    app = create_app(root=root, db_path=tmp_path / "sync_conflict.db")
    client = TestClient(app)

    envelope = json.loads((root / "shared" / "samples" / "sample_sync_envelope.json").read_text(encoding="utf-8"))
    sample_recipe = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
    envelope["payload"]["changes"][0]["body"] = sample_recipe
    envelope["payload"]["changes"][0]["updated_at_utc"] = "2026-04-15T00:20:00Z"
    first = client.post("/sync/push", json=envelope)
    assert first.status_code == 200

    stale = json.loads(json.dumps(envelope))
    stale["request_id"] = "123e4567-e89b-12d3-a456-426614174102"
    stale["payload"]["changes"][0]["updated_at_utc"] = "2026-04-15T00:10:00Z"
    second = client.post("/sync/push", json=stale)
    assert second.status_code == 200
    result = second.json()["payload"]["results"][0]
    assert result["status"] == "conflict"


def test_sync_collection_change_roundtrip(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    app = create_app(root=root, db_path=tmp_path / "sync_collection.db")
    client = TestClient(app)
    push = {
        "sync_protocol_version": 1,
        "request_id": "123e4567-e89b-12d3-a456-4266141741aa",
        "session_id": "desktop-mobile-session-1",
        "device_id": "android-pixel-01",
        "sent_at_utc": "2026-04-15T00:00:10Z",
        "payload": {
            "since_cursor": None,
            "next_cursor": None,
            "changes": [
                {
                    "entity_type": "collection",
                    "entity_id": "123e4567-e89b-12d3-a456-4266141741ab",
                    "op": "upsert",
                    "entity_version": 1,
                    "updated_at_utc": "2026-04-15T00:00:10Z",
                    "body": {
                        "id": "123e4567-e89b-12d3-a456-4266141741ab",
                        "name": "Weeknight",
                        "created_at": "2026-04-15T00:00:10Z",
                    },
                    "source_scope": "local",
                }
            ],
        },
        "errors": [],
    }
    push_response = client.post("/sync/push", json=push)
    assert push_response.status_code == 200
    pull_response = client.post(
        "/sync/pull",
        json={
            "sync_protocol_version": 1,
            "request_id": "123e4567-e89b-12d3-a456-4266141741ac",
            "session_id": "desktop-mobile-session-1",
            "device_id": "android-pixel-01",
            "sent_at_utc": "2026-04-15T00:01:10Z",
            "payload": {"since_cursor": None, "next_cursor": None, "changes": []},
            "errors": [],
        },
    )
    assert pull_response.status_code == 200
    changes = pull_response.json()["payload"]["changes"]
    assert any(change["entity_type"] == "collection" for change in changes)


def test_sync_meal_plan_change_roundtrip(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    app = create_app(root=root, db_path=tmp_path / "sync_meal_plan.db")
    client = TestClient(app)
    push = {
        "sync_protocol_version": 1,
        "request_id": "123e4567-e89b-12d3-a456-4266141741ad",
        "session_id": "desktop-mobile-session-1",
        "device_id": "android-pixel-01",
        "sent_at_utc": "2026-04-15T00:00:10Z",
        "payload": {
            "since_cursor": None,
            "next_cursor": None,
            "changes": [
                {
                    "entity_type": "meal_plan",
                    "entity_id": "123e4567-e89b-12d3-a456-4266141741ae",
                    "op": "upsert",
                    "entity_version": 1,
                    "updated_at_utc": "2026-04-15T00:00:10Z",
                    "body": {
                        "id": "123e4567-e89b-12d3-a456-4266141741ae",
                        "name": "Week Plan",
                        "created_at": "2026-04-15T00:00:10Z",
                    },
                    "source_scope": "local",
                }
            ],
        },
        "errors": [],
    }
    assert client.post("/sync/push", json=push).status_code == 200
    pull_response = client.post(
        "/sync/pull",
        json={
            "sync_protocol_version": 1,
            "request_id": "123e4567-e89b-12d3-a456-4266141741af",
            "session_id": "desktop-mobile-session-1",
            "device_id": "android-pixel-01",
            "sent_at_utc": "2026-04-15T00:01:10Z",
            "payload": {"since_cursor": None, "next_cursor": None, "changes": []},
            "errors": [],
        },
    )
    assert pull_response.status_code == 200
    changes = pull_response.json()["payload"]["changes"]
    assert any(change["entity_type"] == "meal_plan" for change in changes)


def test_sync_recipe_user_state_roundtrip(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    app = create_app(root=root, db_path=tmp_path / "sync_user_state.db")
    client = TestClient(app)
    push = {
        "sync_protocol_version": 1,
        "request_id": "123e4567-e89b-12d3-a456-4266141741b1",
        "session_id": "desktop-mobile-session-1",
        "device_id": "android-pixel-01",
        "sent_at_utc": "2026-04-15T00:00:10Z",
        "payload": {
            "since_cursor": None,
            "next_cursor": None,
            "changes": [
                {
                    "entity_type": "recipe_user_state",
                    "entity_id": "123e4567-e89b-12d3-a456-4266141741b2",
                    "op": "upsert",
                    "entity_version": 1,
                    "updated_at_utc": "2026-04-15T00:00:10Z",
                    "body": {
                        "recipe_id": "123e4567-e89b-12d3-a456-4266141741b2",
                        "is_favorite": True,
                        "last_opened_at": "2026-04-15T00:00:10Z",
                        "last_cooked_at": None,
                        "open_count": 2,
                        "cook_count": 0,
                        "pinned": False,
                    },
                    "source_scope": "local",
                }
            ],
        },
        "errors": [],
    }
    assert client.post("/sync/push", json=push).status_code == 200
    pull_response = client.post(
        "/sync/pull",
        json={
            "sync_protocol_version": 1,
            "request_id": "123e4567-e89b-12d3-a456-4266141741b3",
            "session_id": "desktop-mobile-session-1",
            "device_id": "android-pixel-01",
            "sent_at_utc": "2026-04-15T00:01:10Z",
            "payload": {"since_cursor": None, "next_cursor": None, "changes": []},
            "errors": [],
        },
    )
    assert pull_response.status_code == 200
    changes = pull_response.json()["payload"]["changes"]
    assert any(change["entity_type"] == "recipe_user_state" for change in changes)

