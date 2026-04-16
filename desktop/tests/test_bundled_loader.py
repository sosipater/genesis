from pathlib import Path

from desktop.app.bundled_loader import BundledContentLoader


def test_bundled_manifest_loads() -> None:
    root = Path(__file__).resolve().parents[2]
    loader = BundledContentLoader(root)
    manifest = loader.load_manifest()
    assert manifest["manifest_version"] == 1
    assert isinstance(manifest["bundled_recipes"], list)

