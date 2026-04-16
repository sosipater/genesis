"""Structured logging baseline for desktop subsystems."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from desktop.app.domain.models import utc_now_iso


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("subsystem", "request_id", "session_id", "device_id", "correlation_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(log_level: str, enable_file_logging: bool, logs_dir: Path) -> None:
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    if enable_file_logging:
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(logs_dir / "desktop.log", maxBytes=1_000_000, backupCount=3)
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)

