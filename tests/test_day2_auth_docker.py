import unittest
import base64
import json
import os
from unittest.mock import patch, MagicMock

# We need to set the environment variables before importing app
os.environ["AUTH_PASSWORD"] = "tmirror2024"

import app
from truth_mirror.caching import EvidenceCache

class TestAuth(unittest.TestCase):
    def setUp(self):
        # Create a mock request handler
        class MockHandler(app.TruthMirrorHandler):
            def __init__(self, request, client_address, server):
                self.headers = {}
                self.path = "/api/status"
                self.rfile = MagicMock()
                self.wfile = MagicMock()
                self._responses = []
                self._headers = []
            
            def send_response(self, code, message=None):
                self._responses.append(code)
                
            def send_header(self, keyword, value):
                self._headers.append((keyword, value))
                
            def end_headers(self):
                pass
                
            def setup(self):
                pass
                
            def finish(self):
                pass
        
        # Disable logging to avoid noise
        self.handler_cls = MockHandler

    def _create_handler(self, headers=None):
        handler = self.handler_cls(None, None, None)
        if headers:
            handler.headers = headers
        return handler

    @patch("app.AUTH_PASSWORD", "tmirror2024")
    def test_missing_auth(self):
        handler = self._create_handler()
        res = handler._check_auth()
        self.assertFalse(res)
        self.assertEqual(handler._responses[0], 401)
        self.assertIn(("WWW-Authenticate", 'Basic realm="Truth Mirror"'), handler._headers)

    @patch("app.AUTH_PASSWORD", "tmirror2024")
    def test_correct_auth(self):
        auth_string = base64.b64encode(b"anyuser:tmirror2024").decode("utf-8")
        handler = self._create_handler({"Authorization": f"Basic {auth_string}"})
        res = handler._check_auth()
        self.assertTrue(res)
        self.assertEqual(len(handler._responses), 0)

    @patch("app.AUTH_PASSWORD", "tmirror2024")
    def test_incorrect_auth(self):
        auth_string = base64.b64encode(b"anyuser:wrongpassword").decode("utf-8")
        handler = self._create_handler({"Authorization": f"Basic {auth_string}"})
        res = handler._check_auth()
        self.assertFalse(res)
        self.assertEqual(handler._responses[0], 401)

    @patch("app.AUTH_PASSWORD", None)
    def test_no_auth_required_if_env_unset(self):
        handler = self._create_handler()
        res = handler._check_auth()
        self.assertTrue(res)


class TestDockerEnv(unittest.TestCase):
    @patch.dict(os.environ, {"CACHE_DB_PATH": "/app/data/custom_cache.db"}, clear=True)
    @patch("sqlite3.connect")
    def test_evidence_cache_reads_env_var(self, mock_connect):
        cache = EvidenceCache()
        self.assertEqual(cache.db_path, "/app/data/custom_cache.db")
        mock_connect.assert_called_with("/app/data/custom_cache.db", timeout=5.0)

if __name__ == "__main__":
    unittest.main()
