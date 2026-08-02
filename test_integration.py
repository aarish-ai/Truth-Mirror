"""
Integration test suite for Truth Mirror.

Includes explicit programmatic assertion functions test_c1_* through test_c14_*
verifying all 14 critical fixes:
- test_c1_geo_credibility_overrides
- test_c2_sparql_injection_prevention
- test_c3_aiohttp_session_reuse
- test_c4_retrieval_timeouts_present
- test_c5_defusedxml_usage
- test_c6_embedding_fallback_handling
- test_c7_auth_enforcement
- test_c8_no_silent_mock_data_in_prod
- test_c9_prompt_sanitization
- test_c10_http_handler_exception_catch
- test_c11_search_planner_order_preservation
- test_c12_domain_matching_precision
- test_c13_publisher_name_matching_precision
- test_c14_thread_safe_gemini_counter

Preserves run_test_claim and the if __name__ == "__main__": block for live HTTP smoke testing.
"""

import os
import time
import json
import base64
import threading
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import requests
import aiohttp
import defusedxml.ElementTree as DefusedET

from truth_mirror.models import EvidenceItem, Entity
from truth_mirror.credibility import CredibilityRegistry
from truth_mirror.kg_verifier import build_sparql_query
import truth_mirror.retrieval_news as r_news
import truth_mirror.retrieval_nonwestern as r_nonwestern
import truth_mirror.retrieval as r_retrieval
from truth_mirror.embeddings import get_gemini_embedding
from truth_mirror.ranking import _semantic_similarity, _cosine_similarity
from truth_mirror.vector_store import VectorStore
from truth_mirror.context_tracker import ContextTracker
from app import TruthMirrorHandler
from truth_mirror.retrieval_fact import (
    GoogleFactCheckConnector,
    SnopesFactCheckScraper,
    WorldBankConnector,
    FREDConnector,
    WikidataSPARQLConnector,
    GovInfoConnector,
)
from truth_mirror.retrieval_archival import (
    WaybackMachineConnector,
    OpenLibraryConnector
)
from truth_mirror.retrieval_quotes import WikiquoteConnector, MillerCenterConnector
from truth_mirror.source_analyzer import SourceAnalyzer, _call_gemini_async, _build_single_prompt
from truth_mirror.search_planner import SearchPlanner
from truth_mirror.geo_orchestrator import GeopoliticalPipeline
from truth_mirror.gemini_analyzer import GeminiAnalyzer
from truth_mirror.triangulation import HostileSourceTriangulator
from truth_mirror.source_registry import get_source_metadata


# ============================================================================
# C1 - C14 Programmatic Integration Tests
# ============================================================================

def test_c1_geo_credibility_overrides(tmp_path):
    """C1: Geo-Credibility Overrides must be loaded and applied when is_geopolitical=True."""
    registry_file = tmp_path / "test_credibility.json"
    registry_file.write_text(
        """{
            "source_type_defaults": {"journalism": 0.78, "official": 0.95},
            "publisher_overrides": {"rt": 0.60, "reuters": 0.90},
            "geo_credibility_overrides": {"rt": 0.40, "cgtn": 0.42}
        }""",
        encoding="utf-8"
    )
    registry = CredibilityRegistry.load(str(registry_file))
    assert registry.geo_credibility_overrides.get("rt") == 0.40
    assert registry.geo_credibility_overrides.get("cgtn") == 0.42

    rt_item = EvidenceItem(
        source_title="RT Article",
        url_or_id="https://rt.com/news/1",
        publisher="RT",
        source_type="journalism",
        excerpt="Excerpt",
        date="2026-01-01"
    )

    # When is_geopolitical=False, publisher_overrides is used (0.60)
    assert registry.score(rt_item, is_geopolitical=False) == 0.60

    # When is_geopolitical=True, geo_credibility_overrides is used (0.40)
    assert registry.score(rt_item, is_geopolitical=True) == 0.40

    reuters_item = EvidenceItem(
        source_title="Reuters Article",
        url_or_id="https://reuters.com/news/1",
        publisher="Reuters",
        source_type="journalism",
        excerpt="Excerpt",
        date="2026-01-01"
    )
    # Reuters not in geo_credibility_overrides; falls through to publisher_overrides (0.90)
    assert registry.score(reuters_item, is_geopolitical=True) == 0.90


def test_c2_sparql_injection_prevention():
    """C2: SPARQL Query escaping and property ID validation to prevent injection."""
    entity_name = 'Test "Entity" \\ with injection'
    property_id = 'P36'
    query = build_sparql_query(entity_name, property_id)
    assert 'mwapi:search "Test \\"Entity\\" \\\\ with injection";' in query
    assert 'wdt:P36' in query

    with pytest.raises(ValueError, match="Invalid property_id"):
        build_sparql_query('France', 'P36; DROP TABLE')

    with pytest.raises(ValueError, match="Invalid property_id"):
        build_sparql_query('France', 'INVALID_P')

    query_valid = build_sparql_query('France', 'P1082')
    assert 'wdt:P1082' in query_valid


def test_c3_aiohttp_session_reuse():
    """C3: Verify async API helpers accept and reuse an external aiohttp.ClientSession."""
    async def _test():
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"candidates": [{"content": {"parts": [{"text": '{"stance": "SUPPORTS"}'}]}}]}
        )

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        
        class MockPostContext:
            async def __aenter__(self):
                return mock_response
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_session.post = MagicMock(return_value=MockPostContext())

        with patch("truth_mirror.key_rotator.get_current_key", return_value="fake_key"):
            result = await _call_gemini_async("test prompt", "gemini-2.5-flash", session=mock_session)

        assert result == '{"stance": "SUPPORTS"}'
        assert mock_session.post.called
        assert not mock_session.close.called

        analyzer = SourceAnalyzer()
        mock_article = EvidenceItem(
            source_title="Test title",
            source_type="journalism",
            publisher="Test publisher",
            date="2026-01-01",
            url_or_id="https://example.com/test",
            excerpt="Test claim snippet text long enough",
        )

        with patch.object(analyzer, "_call_groq_batch", return_value=[]):
            res = await analyzer.analyze_all([mock_article], "Test claim snippet", session=mock_session)
            assert isinstance(res, list)

    asyncio.run(_test())


def test_c4_retrieval_timeouts_present():
    """C4: Verify all requests.get calls in retrieval modules supply explicit timeout parameter."""
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {}

        GoogleFactCheckConnector("fake_key").search_claims("query")
        assert mock_get.call_args[1].get("timeout") == 15

        mock_get.reset_mock()
        SnopesFactCheckScraper().search("query")
        assert mock_get.call_args[1].get("timeout") == 15

        mock_get.reset_mock()
        WorldBankConnector().get_indicator_data("USA", "SP.POP.TOTL")
        assert mock_get.call_args[1].get("timeout") == 15

        mock_get.reset_mock()
        FREDConnector("fake_key").get_series_observations("GDP")
        assert mock_get.call_args[1].get("timeout") == 15

        mock_get.reset_mock()
        WikidataSPARQLConnector().query("SELECT * WHERE {}")
        assert mock_get.call_args[1].get("timeout") == 15

        mock_get.reset_mock()
        GovInfoConnector("fake_key").search_packages("budget")
        assert mock_get.call_args[1].get("timeout") == 15

        mock_get.reset_mock()
        WaybackMachineConnector().get_archived_url("https://example.com")
        assert mock_get.call_args[1].get("timeout") == 15

        mock_get.reset_mock()
        OpenLibraryConnector().search_books("Python")
        assert mock_get.call_args[1].get("timeout") == 15

        mock_get.reset_mock()
        WikiquoteConnector().search_quote("Einstein", "relativity")
        assert mock_get.call_args[1].get("timeout") == 15


def test_c5_defusedxml_usage():
    """C5: Verify defusedxml is imported and used instead of unsafe xml.etree.ElementTree."""
    assert r_news.ET is DefusedET
    assert r_nonwestern.ET is DefusedET
    assert r_retrieval.ET is DefusedET


def test_c6_embedding_fallback_handling(tmp_path):
    """C6: get_gemini_embedding returns None on failure instead of zero vector poisoning."""
    with patch("truth_mirror.embeddings.get_current_key", return_value=None):
        res = get_gemini_embedding("sample text")
        assert res is None, "Should return None on embedding failure"

    assert _cosine_similarity(None, [0.1] * 768) == 0.0
    assert _cosine_similarity([0.1] * 768, None) == 0.0

    with patch("truth_mirror.ranking.get_gemini_embedding", return_value=None):
        score = _semantic_similarity("claim", "evidence excerpt")
        assert score == 0.0

    with patch("truth_mirror.vector_store.get_gemini_embedding", return_value=None):
        vs = VectorStore(backend="faiss")
        vs.store("doc1", "sample text")
        assert vs.index.ntotal == 0, "Doc should not be indexed when embedding is None"
        res_vs = vs.search("query")
        assert res_vs == [], "Search should return empty list when embedding is None"

    with patch("truth_mirror.context_tracker.get_gemini_embedding", return_value=None):
        history_file = str(tmp_path / "history.json")
        tracker = ContextTracker(history_file=history_file)
        tracker.history = [
            {"claim": "Old Claim 1", "entities": ["http://e1"], "timestamp": 100, "verdict": "TRUE"}
        ]
        entities = [Entity(name="E1", uri="http://e1")]
        context = tracker.track_claim("New Claim 1", entities)
        assert context is not None


def test_c7_auth_enforcement(monkeypatch):
    """C7: Verify Auth enforcement rejecting missing/invalid credentials."""
    import app
    handler = MagicMock(spec=TruthMirrorHandler)
    handler.headers = {}
    handler.wfile = MagicMock()
    
    result = app._check_session(handler)
    assert result is False
    handler.send_response.assert_called_with(401)

    monkeypatch.setattr("app.AUTH_PASSWORD", "secret123")
    monkeypatch.setattr("app.AUTH_USERNAMES", {"admin"})
    handler_valid = MagicMock(spec=TruthMirrorHandler)
    handler_valid.wfile = MagicMock()
    
    # Simulate a valid login session
    token = app._create_session("admin")
    handler_valid.headers = {"Authorization": f"Bearer {token}"}
    
    result_valid = app._check_session(handler_valid)
    assert result_valid is True


def test_c8_no_silent_mock_data_in_prod(monkeypatch):
    """C8: Connectors return empty list [] without mock data."""
    monkeypatch.setenv("TM_TEST_MODE", "true")

    gfc = GoogleFactCheckConnector(api_key=None)
    assert gfc.search_claims("test query") == []

    fred = FREDConnector(api_key=None)
    assert fred.get_series_observations("GDP") == []

    govinfo = GovInfoConnector(api_key=None)
    assert govinfo.search_packages("budget") == []

    assert OpenLibraryConnector().search_books("query") == []
    assert MillerCenterConnector().search_presidential_speeches("Lincoln", "query") == []

    monkeypatch.setenv("TM_TEST_MODE", "true")
    assert len(gfc.search_claims("test query")) > 0
    assert len(MillerCenterConnector().search_presidential_speeches("Lincoln", "query")) > 0


def test_c9_prompt_sanitization():
    """C9: Verify prompt injection sanitization escaping triple backticks and XML wrapping."""
    article = EvidenceItem(
        source_title="Title with ``` injection",
        source_type="journalism",
        publisher="TestNews",
        date="2026-07-24",
        url_or_id="https://test.com/news",
        excerpt="Excerpt with ``` and harmful instructions"
    )
    claim = "Claim with ``` and injection instructions"
    
    prompt = _build_single_prompt(article, claim)
    
    assert "```" not in prompt
    assert "` ` `" in prompt
    assert "<untrusted_content>Claim with ` ` ` and injection instructions</untrusted_content>" in prompt
    assert "<untrusted_content>Title with ` ` ` injection</untrusted_content>" in prompt
    assert "<untrusted_content>Excerpt with ` ` ` and harmful instructions</untrusted_content>" in prompt


def test_c10_http_handler_exception_catch():
    """C10: Verify TruthMirrorHandler.do_POST handles general pipeline exception gracefully with HTTP 500."""
    handler = TruthMirrorHandler.__new__(TruthMirrorHandler)
    handler.headers = {"Content-Length": "35"}
    
    req_body = b'{"claim": "Simulated error claim"}'
    handler.rfile = MagicMock()
    handler.rfile.read.return_value = req_body
    handler.path = "/api/verify"

    monkeypatch.setattr("app._check_session", MagicMock(return_value=True))

    written_payloads = []
    def mock_write_json(payload, status=200):
        written_payloads.append((payload, status))

    handler._write_json = mock_write_json

    mock_pipeline = MagicMock()
    mock_pipeline.verify.side_effect = RuntimeError("Simulated pipeline crash")
    handler.pipeline = mock_pipeline

    handler.do_POST()

    assert len(written_payloads) == 1
    payload, status = written_payloads[0]
    assert status == 500
    assert payload["error"] == "Internal server error during analysis"
    assert "Simulated pipeline crash" in payload["details"]


def test_c11_search_planner_order_preservation():
    """C11: Verify SearchPlanner and GeopoliticalPipeline preserve exact query submission order."""
    mock_retriever = MagicMock()
    
    def mock_retrieve(query, claim_type=None):
        if query == "query1":
            time.sleep(0.05)  # Slower query
            return [EvidenceItem(source_title="Result Q1", source_type="journalism", publisher="P1", date="2026-01-01", url_or_id="http://q1.com", excerpt="E1")]
        else:
            return [EvidenceItem(source_title="Result Q2", source_type="journalism", publisher="P2", date="2026-01-01", url_or_id="http://q2.com", excerpt="E2")]

    mock_retriever.retrieve.side_effect = mock_retrieve

    mock_qgen = MagicMock()
    mock_qgen.generate_queries.return_value = ["query1", "query2"]

    planner = SearchPlanner(mock_retriever, mock_qgen)
    results, queries_used = planner.retrieve_for_subclaim("test subclaim", "geopolitical", False)

    assert queries_used == ["query1", "query2"]
    assert len(results) == 2
    assert results[0].url_or_id == "http://q1.com"
    assert results[1].url_or_id == "http://q2.com"

    pipeline = GeopoliticalPipeline.__new__(GeopoliticalPipeline)
    mock_retriever_geo = MagicMock()

    def mock_retrieve_geo(query, claim_subtype, use_wikinews):
        if query == "q_first":
            time.sleep(0.05)
            return [EvidenceItem(source_title="First", source_type="journalism", publisher="P", date="2026-01-01", url_or_id="http://first.com", excerpt="E")]
        else:
            return [EvidenceItem(source_title="Second", source_type="journalism", publisher="P", date="2026-01-01", url_or_id="http://second.com", excerpt="E")]

    mock_retriever_geo.retrieve.side_effect = mock_retrieve_geo
    pipeline.retriever = mock_retriever_geo

    results_geo = pipeline._parallel_retrieve(["q_first", "q_second"], "conflict")
    assert len(results_geo) == 2
    assert results_geo[0].url_or_id == "http://first.com"
    assert results_geo[1].url_or_id == "http://second.com"


def test_c12_domain_matching_precision():
    """C12: Domain matching must be exact or dot-prefixed suffix to prevent false matches like rt.com in art.com."""
    triangulator = HostileSourceTriangulator()
    assert triangulator._determine_source_stance("https://art.com/article") == "unknown"
    assert triangulator._determine_source_stance("https://smart.com/article") == "unknown"
    assert triangulator._determine_source_stance("https://rt.com/article") == "state_sponsored_russia"
    assert triangulator._determine_source_stance("https://news.rt.com/article") == "state_sponsored_russia"

    meta_art = get_source_metadata("https://art.com/page")
    assert meta_art.get("alignment") != "eastern"

    meta_rt = get_source_metadata("https://rt.com/page")
    assert meta_rt.get("alignment") == "eastern"

    meta_sub_rt = get_source_metadata("https://sub.rt.com/page")
    assert meta_sub_rt.get("alignment") == "eastern"


def test_c13_publisher_name_matching_precision():
    """C13: Publisher matching must use exact match or token-set comparison, not substring containment."""
    meta_time = get_source_metadata("https://unknown-domain-x.com", publisher="Time")
    assert meta_time.get("name") != "New York Times"

    meta_nyt = get_source_metadata("https://unknown-domain-x.com", publisher="New York Times")
    assert meta_nyt.get("name") == "New York Times"

    meta_nyt_permuted = get_source_metadata("https://unknown-domain-x.com", publisher="York New Times")
    assert meta_nyt_permuted.get("name") == "New York Times"


def test_c14_thread_safe_gemini_counter():
    """C14: Verify GeminiAnalyzer._call_count increments safely across concurrent threads."""
    GeminiAnalyzer.reset_call_count()
    assert GeminiAnalyzer._call_count == 0

    with patch.dict("os.environ", {"MAX_GEMINI_CALLS_PER_QUERY": "10"}):
        analyzer = GeminiAnalyzer()
        analyzer.enabled = False

        def call_synthesize():
            analyzer.synthesize("claim", [EvidenceItem(source_title="Title", source_type="journalism", publisher="Pub", date="2026-01-01", url_or_id="http://url.com", excerpt="Snippet")])

        threads = [threading.Thread(target=call_synthesize) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert GeminiAnalyzer._call_count == 10

    GeminiAnalyzer.reset_call_count()
    assert GeminiAnalyzer._call_count == 0


# ============================================================================
# HTTP Smoke Test Runner for Manual / Main Execution
# ============================================================================

def run_test_claim(claim_text):
    print(f"\n--- Testing: {claim_text} ---")
    start = time.time()
    from dotenv import load_dotenv
    load_dotenv()
    try:
        test_user = os.environ.get("AUTH_USERNAME", "admin")
        test_pass = os.environ.get("AUTH_PASSWORD", "secret")
        resp = requests.post(
            "http://127.0.0.1:8080/api/verify",
            json={"claim": claim_text},
            auth=(test_user, test_pass),
            timeout=300
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "verdict_data" in data, "Missing verdict_data in response"
        assert "verdict" in data["verdict_data"], "Missing verdict in verdict_data"
        print(f"Status Code: {resp.status_code}")
        
        verdict = data.get("verdict_data", {}).get("verdict", "N/A")
        print(f"Verdict: {verdict}")
        
        queries = data.get("search_queries", [])
        print(f"Generated Queries: {json.dumps(queries, indent=2)}")
        
        analyses = data.get("source_analyses", [])
        print(f"Analyzed {len(analyses)} sources.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print(f"Elapsed: {time.time() - start:.2f}s")


if __name__ == "__main__":
    run_test_claim("India is attacking Pakistan as of July 2026")
    run_test_claim("India is attacking Pakistan")
