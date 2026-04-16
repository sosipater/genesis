from pathlib import Path

from desktop.app.persistence.database import Database


def test_normalized_tables_exist(tmp_path: Path) -> None:
    db = Database(tmp_path / "schema.db")
    try:
        tables = {
            row["name"]
            for row in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        expected = {
            "recipes",
            "recipe_equipment",
            "recipe_ingredients",
            "recipe_steps",
            "step_links",
            "step_timers",
            "media_assets",
            "sync_state",
            "sync_conflicts",
        }
        assert expected.issubset(tables)
        assert "local_recipes" not in tables
    finally:
        db.close()

