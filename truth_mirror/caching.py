"""SQLite-based cache for Truth Mirror."""

from __future__ import annotations

import json
import sqlite3
import os
from typing import Any
from pathlib import Path


class EvidenceCache:
    """SQLite cache to persist retrieved evidence items."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.environ.get("CACHE_DB_PATH", ".tm_cache.db")
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Create a connection with WAL mode and a 5-second busy timeout."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS result_cache (
                    key TEXT PRIMARY KEY,
                    data TEXT,
                    temporal_type TEXT DEFAULT 'current_state',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME
                )
                """
            )
        self.cleanup_expired_results()

    def get(self, key: str) -> list[dict[str, Any]] | None:
        """Get cached data for a key."""
        with self._connect() as conn:
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
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, data) VALUES (?, ?)",
                (key, json.dumps(data)),
            )

    def get_result(self, claim_key: str) -> dict | None:
        """Get cached pipeline result if it exists and has not expired."""
        from datetime import datetime, timezone
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT data FROM result_cache
                WHERE key = ?
                AND expires_at > ?
                """,
                (claim_key, datetime.now(timezone.utc).isoformat())
            )
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return None
        return None

    def set_result(
        self,
        claim_key: str,
        data: dict,
        temporal_type: str = "current_state"
    ) -> None:
        """Cache a pipeline result with TTL based on temporal type."""
        from datetime import datetime, timedelta, timezone

        TTL_HOURS = {
            "current_state": 6,
            "recent_development": 12,
            "historical_completed": 72,
            "specific_incident": 24,
        }
        hours = TTL_HOURS.get(temporal_type, 12)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO result_cache
                (key, data, temporal_type, timestamp, expires_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (claim_key, json.dumps(data), temporal_type, expires_at)
            )

    def cleanup_expired_results(self) -> int:
        """Delete expired result cache entries. Returns count deleted."""
        from datetime import datetime, timezone
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM result_cache WHERE expires_at < ?",
                (datetime.now(timezone.utc).isoformat(),)
            )
            return cursor.rowcount

    @staticmethod
    def normalize_claim_key(claim: str) -> str:
        """
        Normalize a claim string into a cache key.
        Lowercases, strips punctuation, collapses whitespace.
        "US is bombing Iran!" and "us is bombing iran" → same key.
        """
        import re
        normalized = claim.lower().strip()
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized
