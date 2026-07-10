import os
import json
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch, MagicMock
from io import BytesIO

# Import modules under test
import truth_mirror.key_rotator as kr
from truth_mirror.embeddings import get_gemini_embedding
from truth_mirror.claim_scope_gate import gate_claim
from truth_mirror.query_generator import QueryGenerator
from truth_mirror.geo_query_generator import GeoQueryGenerator

class TestTruthMirrorPipeline(unittest.TestCase):

    def setUp(self):
        # Save original state of key_rotator
        self._orig_keys = kr._gemini_keys
        self._orig_cycle = kr._gemini_key_cycle
        self._orig_curr = kr._current_key
        self._orig_env_keys = os.environ.get("GEMINI_API_KEYS")
        self._orig_env_key = os.environ.get("GEMINI_API_KEY")
        self._orig_or_key = os.environ.get("OPENROUTER_API_KEY")
        self._orig_groq_key = os.environ.get("GROQ_API_KEY")

    def tearDown(self):
        # Restore key_rotator state
        kr._gemini_keys = self._orig_keys
        kr._gemini_key_cycle = self._orig_cycle
        kr._current_key = self._orig_curr
        if self._orig_env_keys is not None:
            os.environ["GEMINI_API_KEYS"] = self._orig_env_keys
        else:
            os.environ.pop("GEMINI_API_KEYS", None)
        if self._orig_env_key is not None:
            os.environ["GEMINI_API_KEY"] = self._orig_env_key
        else:
            os.environ.pop("GEMINI_API_KEY", None)
        if self._orig_or_key is not None:
            os.environ["OPENROUTER_API_KEY"] = self._orig_or_key
        else:
            os.environ.pop("OPENROUTER_API_KEY", None)
        if self._orig_groq_key is not None:
            os.environ["GROQ_API_KEY"] = self._orig_groq_key
        else:
            os.environ.pop("GROQ_API_KEY", None)

    @patch("urllib.request.urlopen")
    def test_embedding_rate_limiting_and_key_rotation(self, mock_urlopen):
        """
        Test that when the Embedding API returns 429/403:
        1. The key is rotated.
        2. The request is retried with the new key.
        3. Fallback is returned only after exhausting attempts.
        """
        # Configure multiple API keys
        os.environ["GEMINI_API_KEYS"] = "KEY_A,KEY_B,KEY_C"
        os.environ.pop("GEMINI_API_KEY", None)
        
        # Reset key rotator state to force re-initialization
        kr._gemini_keys = []
        kr._gemini_key_cycle = None
        kr._current_key = None
        
        # Mock API calls:
        # Attempt 1: 429 error -> rotates to KEY_B
        # Attempt 2: 429 error -> rotates to KEY_C
        # Attempt 3: Success -> returns embedding
        
        # We need to create mock response and HTTPError objects
        err_429 = urllib.error.HTTPError(
            url="http://fake.api",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=None
        )
        
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "embedding": {"values": [0.1, 0.2, 0.3]}
        }).encode("utf-8")
        
        mock_urlopen.side_effect = [err_429, err_429, mock_resp]
        
        # Initial key should be KEY_A
        self.assertEqual(kr.get_current_key(), "KEY_A")
        
        # Call the embedding function
        emb = get_gemini_embedding("test query")
        
        # Check that we received the correct non-fallback embedding
        self.assertEqual(emb, [0.1, 0.2, 0.3])
        
        # Check that key rotated to KEY_C
        self.assertEqual(kr.get_current_key(), "KEY_C")
        self.assertEqual(os.environ["GEMINI_API_KEY"], "KEY_C")
        self.assertEqual(mock_urlopen.call_count, 3)

        # Verify that all attempts failing returns fallback
        mock_urlopen.reset_mock()
        mock_urlopen.side_effect = [err_429] * 5
        emb_fallback = get_gemini_embedding("another query")
        self.assertEqual(emb_fallback, [0.0] * 768)
        self.assertEqual(mock_urlopen.call_count, 5)

    @patch("truth_mirror.claim_scope_gate._call_groq")
    @patch("urllib.request.urlopen")
    def test_openrouter_fallback_when_gemini_key_blocked_or_missing(self, mock_urlopen, mock_call_groq):
        """
        Test that when Groq and Gemini calls fail (due to being blocked or missing keys),
        the pipeline falls back to OpenRouter.
        """
        # Ensure OpenRouter API key is set
        os.environ["OPENROUTER_API_KEY"] = "fake-openrouter-key"
        # Ensure Gemini API keys are configured (so it tries them)
        os.environ["GEMINI_API_KEYS"] = "FAKE_GEMINI_KEY"
        
        kr._gemini_keys = []
        kr._gemini_key_cycle = None
        kr._current_key = None
        
        # Groq returns None (fail)
        mock_call_groq.return_value = None
        
        # Gemini urlopen raises a 400 error (blocked key or bad request)
        err_400 = urllib.error.HTTPError(
            url="http://fake.gemini.api",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=None
        )
        
        # OpenRouter returns a successful response
        openrouter_response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "is_geopolitical": True,
                            "topic_reason": "simulated openrouter fallback",
                            "involved_parties": ["US", "Iran"],
                            "claim_subtype": "military",
                            "estimated_timeframe": "2026",
                            "in_temporal_scope": True,
                            "temporal_reason": "simulated"
                        })
                    }
                }
            ]
        }
        
        mock_openrouter_resp = MagicMock()
        mock_openrouter_resp.read.return_value = json.dumps(openrouter_response_data).encode("utf-8")
        
        # urlopen side effect:
        # Attempt 1, 2, 3: Gemini attempts (400 error)
        # Attempt 4: OpenRouter attempt (succeeds)
        mock_urlopen.side_effect = [err_400, err_400, err_400, mock_openrouter_resp]
        
        # Call the gate claim function
        res = gate_claim("The US attacked Iran in 2026")
        
        # Verify the fallback worked and parsed the OpenRouter response
        self.assertIsNotNone(res)
        self.assertTrue(res.is_geopolitical)
        self.assertEqual(res.topic_reason, "simulated openrouter fallback")
        self.assertEqual(res.involved_parties, ["US", "Iran"])
        self.assertEqual(res.claim_subtype, "military")

    @patch("requests.post")
    def test_prompt_time_blindness_with_dates(self, mock_post):
        """
        Verify that:
        1. When a claim contains a date and is evaluated, the pipeline respects the date
           and does NOT hardcode the current month/year (time-blindness).
        2. Geopolitical queries generated are broad and timeline-agnostic (do not include current date).
        """
        # Case A: QueryGenerator (general) with has_date=True
        # We mock the Ollama response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": json.dumps(["US election 2024 results", "Trump Biden vote 2024", "presidential race 2024"])}
        mock_post.return_value = mock_resp
        
        qgen = QueryGenerator()
        
        # We pass has_date=True. Let's inspect the prompt passed to Ollama.
        qgen.generate_queries("US election in 2024", has_date=True)
        
        # Get the prompt that was sent to requests.post
        call_args, call_kwargs = mock_post.call_args
        prompt_sent = call_kwargs["json"]["prompt"]
        
        # Prompt should instruct to respect the date and NOT contain current month/year instructions
        self.assertIn("The claim already has a date. Respect it.", prompt_sent)
        self.assertNotIn("Add '", prompt_sent)
        
        # Case B: QueryGenerator with has_date=False
        # Prompt should ask to append the current date
        qgen.generate_queries("US election", has_date=False)
        call_args, call_kwargs = mock_post.call_args
        prompt_sent_no_date = call_kwargs["json"]["prompt"]
        self.assertIn("queries needing current information", prompt_sent_no_date)
        
        # Case C: GeoQueryGenerator (geopolitical)
        # Geopolitical query generation must explicitly instruct to avoid hardcoding dates
        geo_qgen = GeoQueryGenerator()
        # Mock Groq to fail so we can see the OpenRouter prompt, or just check the prompt directly.
        # Let's verify the prompt instruction template directly.
        date_instruction = "Generate search queries that are broad and timeline-agnostic. Do not include specific dates, months, or years in the queries.\n\n"
        self.assertIn(date_instruction, geo_qgen.generate.__doc__ or "") # Wait, let's verify where it is defined.
        
        # We can also call generate and mock requests.post to check what prompt it gets
        mock_post.reset_mock()
        mock_resp_geo = MagicMock()
        mock_resp_geo.status_code = 200
        mock_resp_geo.json.return_value = {
            "choices": [{"message": {"content": json.dumps(["US Iran conflict news", "official statements US Iran military", "regional reaction US Iran"])}}]
        }
        mock_post.return_value = mock_resp_geo
        
        # Set OPENROUTER_API_KEY so it tries to call OpenRouter
        os.environ["OPENROUTER_API_KEY"] = "fake-key"
        os.environ.pop("GROQ_API_KEY", None)
        
        geo_qgen.generate("The US attacked Iran in February 2026", ["US", "Iran"], "military")
        
        # Inspect prompt
        call_args, call_kwargs = mock_post.call_args
        # It's an OpenRouter chat call, so let's look at messages
        messages = call_kwargs["json"]["messages"]
        user_content = messages[0]["content"]
        
        self.assertIn("Do not include specific dates, months, or years in the queries", user_content)

if __name__ == "__main__":
    unittest.main()
