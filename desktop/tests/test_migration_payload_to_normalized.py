import json
import sqlite3
from pathlib import Path

from desktop.app.domain.models import utc_now_iso
from desktop.app.persistence.migrations import apply_migrations


def test_migrates_payload_table_to_normalized(tmp_path: Path) -> None:
    db_path = tmp_path / "migrate.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            CREATE TABLE local_recipes (
              id TEXT PRIMARY KEY,
              payload_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL
            );
            """
        )
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (1, ?)", (utc_now_iso(),))

        root = Path(__file__).resolve().parents[2]
        payload = json.loads((root / "shared" / "samples" / "sample_recipe.json").read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO local_recipes(id, payload_json, updated_at, deleted_at) VALUES (?, ?, ?, NULL)",
            (payload["id"], json.dumps(payload), payload["updated_at"]),
        )
        conn.commit()

        version = apply_migrations(conn, utc_now_iso())
        assert version == 13
        tables = {
            row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "local_recipes" not in tables

        recipe_row = conn.execute("SELECT title FROM recipes WHERE id=?", (payload["id"],)).fetchone()
        assert recipe_row is not None
        assert recipe_row["title"] == payload["title"]
        ingredient_count = conn.execute(
            "SELECT COUNT(*) AS count FROM recipe_ingredients WHERE recipe_id=?",
            (payload["id"],),
        ).fetchone()["count"]
        assert ingredient_count == 1
    finally:
        conn.close()

