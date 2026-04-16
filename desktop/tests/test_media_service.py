from pathlib import Path

from desktop.app.persistence.database import Database
from desktop.app.persistence.recipe_repository import RecipeRepository
from desktop.app.services.media_service import MediaService


def test_media_import_and_remove(tmp_path: Path) -> None:
    db = Database(tmp_path / "media.db")
    try:
        repo = RecipeRepository(db.conn)
        service = MediaService(repo, tmp_path / "media")
        source = tmp_path / "sample.jpg"
        source.write_bytes(b"fake-image-bytes")
        asset = service.import_for_owner("recipe_cover", "recipe-1", source)
        assert asset["id"]
        stored = repo.get_media_asset(asset["id"])
        assert stored is not None
        resolved = service.resolve_media_path(asset["id"])
        assert resolved is not None and resolved.exists()

        service.remove_media(asset["id"])
        assert repo.get_media_asset(asset["id"]) is None
    finally:
        db.close()


def test_media_validation_rejects_large_or_non_image(tmp_path: Path) -> None:
    db = Database(tmp_path / "media.db")
    try:
        repo = RecipeRepository(db.conn)
        service = MediaService(repo, tmp_path / "media")
        text_file = tmp_path / "notes.txt"
        text_file.write_text("not an image", encoding="utf-8")
        try:
            service.import_for_owner("recipe_cover", "recipe-1", text_file)
            assert False, "Expected non-image validation error"
        except ValueError as exc:
            assert "Unsupported media type" in str(exc)
    finally:
        db.close()
