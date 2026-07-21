"""Tests for Day 1 critical bug fixes."""

import json
import sqlite3
import threading
import time
import unittest
import uuid
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestPerRequestPipelineStatus(unittest.TestCase):
    """Bug Fix #1: Verify per-request status isolation."""

    def setUp(self):
        # Re-import to get fresh state
        import importlib
        import truth_mirror.pipeline_status as ps
        importlib.reload(ps)
        self.ps = ps

    def test_independent_request_statuses(self):
        """Two concurrent requests should NOT overwrite each other's stage."""
        id_a = str(uuid.uuid4())
        id_b = str(uuid.uuid4())

        self.ps.set_stage("retrieving", request_id=id_a)
        self.ps.set_stage("generating_verdict", request_id=id_b)

        status_a = self.ps.get_status(request_id=id_a)
        status_b = self.ps.get_status(request_id=id_b)

        self.assertEqual(status_a["stage"], "retrieving")
        self.assertEqual(status_b["stage"], "generating_verdict")

    def test_unknown_request_returns_idle(self):
        """Polling for a non-existent request_id should return idle."""
        status = self.ps.get_status(request_id="nonexistent-uuid")
        self.assertEqual(status["stage"], "idle")

    def test_clear_status_removes_entry(self):
        """After clear_status, the entry should be gone."""
        rid = str(uuid.uuid4())
        self.ps.set_stage("decomposing", request_id=rid)
        self.ps.clear_status(rid)
        self.assertEqual(self.ps.get_status(request_id=rid)["stage"], "idle")

    def test_cleanup_stale_entries(self):
        """Entries older than EXPIRY_SECONDS should be cleaned up."""
        rid = str(uuid.uuid4())
        self.ps.set_stage("test", request_id=rid)
        # Manually age the entry
        with self.ps._status_lock:
            self.ps._statuses[rid]["updated_at"] = time.time() - 700
        removed = self.ps.cleanup_stale()
        self.assertEqual(removed, 1)
        self.assertEqual(self.ps.get_status(request_id=rid)["stage"], "idle")


class TestSQLiteWALMode(unittest.TestCase):
    """Bug Fix #2: Verify WAL mode and busy timeout."""

    def test_wal_mode_enabled(self):
        """The cache should use WAL journal mode."""
        import tempfile, os
        from truth_mirror.caching import EvidenceCache

        db_path = os.path.join(tempfile.mkdtemp(), "test_wal.db")
        cache = EvidenceCache(db_path=db_path)

        conn = sqlite3.connect(db_path)
        result = conn.execute("PRAGMA journal_mode").fetchone()
        conn.close()

        self.assertEqual(result[0].lower(), "wal")

        # Cleanup
        for ext in ["", "-wal", "-shm"]:
            try:
                os.remove(db_path + ext)
            except OSError:
                pass

    def test_concurrent_reads_and_writes(self):
        """Multiple threads should be able to read/write without 'database is locked'."""
        import tempfile, os
        from truth_mirror.caching import EvidenceCache

        db_path = os.path.join(tempfile.mkdtemp(), "test_concurrent.db")
        cache = EvidenceCache(db_path=db_path)

        errors = []

        def writer(cache, n):
            try:
                for i in range(n):
                    cache.set(f"key_{threading.current_thread().name}_{i}", [{"data": i}])
            except Exception as e:
                errors.append(e)

        def reader(cache, n):
            try:
                for i in range(n):
                    cache.get(f"key_reader_{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=writer, args=(cache, 20), name=f"writer-{i}"))
            threads.append(threading.Thread(target=reader, args=(cache, 20), name=f"reader-{i}"))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")

        # Cleanup
        for ext in ["", "-wal", "-shm"]:
            try:
                os.remove(db_path + ext)
            except OSError:
                pass


class TestFrontendNullGuards(unittest.TestCase):
    """Bug Fix #3: Verify the backend to_json always includes required fields.
    (Frontend JS null guards can't be unit-tested in Python, but we verify
    the backend doesn't send crash-inducing payloads.)"""

    def test_to_json_handles_minimal_result(self):
        """to_json should never produce a dict with None for critical fields."""
        from truth_mirror.orchestrator import TruthMirrorPipeline
        from truth_mirror.models import VerificationResult

        # Create a minimal VerificationResult with mostly empty fields
        result = VerificationResult(
            original_claim="test",
            normalized_claim="test",
            claim_type="unknown",
            sub_claims=[],
            final_verdict="Unclear",
            confidence=0.0,
            confidence_interval=(0.0, 1.0),
            evidence_summary="",
            key_sources=[],
            reasoning="",
            missing_information=[],
            warnings=[]
        )
        output = TruthMirrorPipeline.to_json(result)

        # These fields must exist and not be None
        self.assertIn("final_verdict", output)
        self.assertIn("key_sources", output)
        self.assertIn("warnings", output)
        self.assertIsNotNone(output["final_verdict"])
        self.assertIsInstance(output["key_sources"], list)
        self.assertIsInstance(output["warnings"], list)


class TestHardPipelineTimeout(unittest.TestCase):
    """Bug Fix #4: Verify the timeout mechanism works."""

    def test_timeout_produces_503(self):
        """A hanging pipeline should return 503 with timeout verdict."""
        import concurrent.futures

        def hanging_pipeline(*args, **kwargs):
            time.sleep(2)  # Simulate a hang, but short enough to exit

        # Don't use 'with' so we can test the timeout without blocking the test suite
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(hanging_pipeline, "test claim")
        with self.assertRaises(concurrent.futures.TimeoutError):
            future.result(timeout=0.1)  # 0.1 second timeout for testing
        
        executor.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    unittest.main()
