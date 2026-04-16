from pathlib import Path

from desktop.app.config import load_app_config


def test_config_loads_and_validates() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_app_config(root)
    assert config.config_version == 1
    assert config.sync["protocol_version"] == 1
    assert config.content_paths["bundled_manifest_path"] == "bundled_content/manifest.json"

