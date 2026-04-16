"""Schema-validated app configuration loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator


@dataclass(slots=True)
class AppConfig:
    config_version: int
    ui: dict
    sync: dict
    logging: dict
    content_paths: dict
    feature_toggles: dict


def load_app_config(root: Path) -> AppConfig:
    config_path = root / "shared" / "contracts" / "app_config.default.json"
    schema_path = root / "shared" / "schemas" / "app_config.schema.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
    return AppConfig(**payload)

