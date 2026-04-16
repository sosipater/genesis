"""Database bootstrap and connection factory."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from desktop.app.domain.models import utc_now_iso
from desktop.app.persistence.migrations import apply_migrations


class Database:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        version = apply_migrations(self._conn, now_iso=utc_now_iso())
        self.schema_version = version

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

