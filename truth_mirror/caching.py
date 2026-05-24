"""SQLite-based cache for Truth Mirror."""

from __future__ import annotations

import json
import sqlite3
from typing import Any
from pathlib import Path


class EvidenceCache:
    """SQLite cache to persist retrieved evidence items."""

    def __init__(self, db_path: str = ".tm_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self, key: str) -> list[dict[str, Any]] | None:
        """Get cached data for a key."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT data FROM cache WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return None
        return None

    def set(self, key: str, data: list[dict[str, Any]]) -> None:
        """Set cache data for a key."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, data) VALUES (?, ?)",
                (key, json.dumps(data)),
            )
