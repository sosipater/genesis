"""FastAPI sync host endpoints."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from jsonschema import Draft202012Validator

from desktop.app.bundled_loader import BundledContentLoader
from desktop.app.config import load_app_config
from desktop.app.domain.models import utc_now_iso
from desktop.app.logging_setup import configure_logging
from desktop.app.persistence.database import Database
from desktop.app.runtime_paths import build_runtime_paths
from desktop.app.sync.service import SyncService
from desktop.app.versioning import APP_VERSION


def create_app(root: Path | None = None, db_path: Path | None = None) -> FastAPI:
    project_root = root or Path(__file__).resolve().parents[3]
    config = load_app_config(project_root)
    runtime_paths = build_runtime_paths(project_root)
    configure_logging(
        log_level=config.logging["level"],
        enable_file_logging=config.logging["file_enabled"],
        logs_dir=runtime_paths.logs_dir,
    )
    logger = logging.getLogger("recipe_forge.startup")
    logger.info("Desktop sync host starting", extra={"subsystem": "startup"})

    database = Database(db_path or runtime_paths.db_path)
    sync_service = SyncService(database.conn, protocol_version=config.sync["protocol_version"])
    bundled_loader = BundledContentLoader(project_root)
    sync_schema = json.loads((project_root / "shared" / "schemas" / "sync_envelope.schema.json").read_text(encoding="utf-8"))
    sync_validator = Draft202012Validator(sync_schema)

    app = FastAPI(title="Recipe Forge Desktop Sync Host", version=APP_VERSION)
    app.state.database = database

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "app": "recipe-forge-desktop-sync-host",
            "schema_version": database.schema_version,
            "sync_protocol_version": config.sync["protocol_version"],
            "timestamp": utc_now_iso(),
        }

    @app.get("/sync/status")
    def sync_status() -> dict[str, Any]:
        status = sync_service.status()
        status["bundled_recipe_count"] = len(bundled_loader.load_manifest()["bundled_recipes"])
        return status

    @app.post("/sync/push")
    def sync_push(envelope: dict[str, Any]) -> dict[str, Any]:
        errors = sorted(sync_validator.iter_errors(envelope), key=lambda e: e.path)
        if errors:
            raise HTTPException(status_code=400, detail=[err.message for err in errors])
        _check_protocol_version(envelope, config.sync["protocol_version"])
        _log_request("push", envelope)
        return sync_service.handle_push(envelope)

    @app.post("/sync/pull")
    def sync_pull(envelope: dict[str, Any]) -> dict[str, Any]:
        errors = sorted(sync_validator.iter_errors(envelope), key=lambda e: e.path)
        if errors:
            raise HTTPException(status_code=400, detail=[err.message for err in errors])
        _check_protocol_version(envelope, config.sync["protocol_version"])
        _log_request("pull", envelope)
        return sync_service.handle_pull(envelope)

    return app


def _check_protocol_version(envelope: dict[str, Any], expected_version: int) -> None:
    if envelope["sync_protocol_version"] != expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"sync_protocol_version mismatch: expected={expected_version}",
        )


def _log_request(direction: str, envelope: dict[str, Any]) -> None:
    logging.getLogger("recipe_forge.sync").info(
        f"Sync {direction} request",
        extra={
            "subsystem": "sync",
            "request_id": envelope["request_id"],
            "session_id": envelope["session_id"],
            "device_id": envelope["device_id"],
            "correlation_id": envelope["request_id"],
        },
    )

