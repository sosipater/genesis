from pathlib import Path

from desktop.app.persistence.database import Database


def test_database_bootstrap_creates_schema(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    try:
        assert db.schema_version >= 1
        row = db.conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        assert row["version"] == db.schema_version
    finally:
        db.close()

