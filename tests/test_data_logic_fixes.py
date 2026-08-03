"""Unit tests for C1, C6, C8, C12, and C13 Data Quality & Logic fixes."""

import os
from unittest.mock import patch
import pytest

from truth_mirror.models import EvidenceItem, Entity
from truth_mirror.credibility import CredibilityRegistry
from truth_mirror.embeddings import get_gemini_embedding, get_gemini_embeddings
from truth_mirror.ranking import _semantic_similarity, _cosine_similarity
from truth_mirror.vector_store import VectorStore
from truth_mirror.context_tracker import ContextTracker
from truth_mirror.retrieval_fact import GoogleFactCheckConnector, FREDConnector, GovInfoConnector, SnopesFactCheckScraper

from truth_mirror.retrieval_quotes import WikiquoteConnector, MillerCenterConnector
from truth_mirror.triangulation import HostileSourceTriangulator
from truth_mirror.source_registry import get_source_metadata


class TestC1GeoCredibilityOverrides:
    """C1: Geo-Credibility Overrides must be loaded and applied when is_geopolitical=True."""

    def test_geo_credibility_overrides_loaded_and_applied(self, tmp_path):
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


class TestC6EmbeddingZeroVectorPoisoning:
    """C6: get_gemini_embedding must return None on failure instead of zero vector [0.0] * 768."""

    @patch("truth_mirror.embeddings.get_current_key", return_value=None)
    def test_embedding_failure_returns_none(self, mock_key):
        res = get_gemini_embedding("sample text")
        assert res is None, "Should return None on embedding failure"

    def test_cosine_similarity_with_none(self):
        assert _cosine_similarity(None, [0.1] * 768) == 0.0
        assert _cosine_similarity([0.1] * 768, None) == 0.0

    @patch("truth_mirror.ranking.get_gemini_embedding", return_value=None)
    def test_semantic_similarity_with_none(self, mock_emb):
        score = _semantic_similarity("claim", "evidence excerpt")
        assert score == 0.0

    @patch("truth_mirror.vector_store.get_gemini_embedding", return_value=None)
    def test_vector_store_handles_none_embedding(self, mock_emb, tmp_path):
        vs = VectorStore(backend="faiss")
        vs.store("doc1", "sample text")
        assert vs.index.ntotal == 0, "Doc should not be indexed when embedding is None"
        res = vs.search("query")
        assert res == [], "Search should return empty list when embedding is None"

    @patch("truth_mirror.context_tracker.get_gemini_embedding", return_value=None)
    def test_context_tracker_handles_none_embedding(self, mock_emb, tmp_path):
        history_file = str(tmp_path / "history.json")
        tracker = ContextTracker(history_file=history_file)
        tracker.history = [
            {"claim": "Old Claim 1", "entities": ["http://e1"], "timestamp": 100, "verdict": "TRUE"}
        ]
        entities = [Entity(name="E1", uri="http://e1")]
        context = tracker.track_claim("New Claim 1", entities)
        assert context is not None


class TestC8SilentProductionMockData:
    """C8: Connectors must return empty list [] in production mode (TM_TEST_MODE != true)."""

    def test_production_mode_returns_empty_lists(self, monkeypatch):
        monkeypatch.setenv("TM_TEST_MODE", "false")

        # Fact connectors with missing API key
        gfc = GoogleFactCheckConnector(api_key=None)
        assert gfc.search_claims("test query") == []

        fred = FREDConnector(api_key=None)
        assert fred.get_series_observations("GDP") == []

        govinfo = GovInfoConnector(api_key=None)
        assert govinfo.search_packages("test query") == []



        # Quote mock connectors
        assert MillerCenterConnector().search_presidential_speeches("Lincoln", "query") == []


class TestC12NaiveDomainMatching:
    """C12: Domain matching must be exact or dot-prefixed suffix to prevent false matches like rt.com in art.com."""

    def test_rt_com_does_not_match_art_com(self):
        triangulator = HostileSourceTriangulator()
        # art.com and smart.com should NOT match rt.com
        assert triangulator._determine_source_stance("https://art.com/article") == "unknown"
        assert triangulator._determine_source_stance("https://smart.com/article") == "unknown"

        # rt.com and subdomains of rt.com SHOULD match
        assert triangulator._determine_source_stance("https://rt.com/article") == "state_sponsored_russia"
        assert triangulator._determine_source_stance("https://news.rt.com/article") == "state_sponsored_russia"

    def test_source_registry_domain_matching(self):
        meta_art = get_source_metadata("https://art.com/page")
        assert meta_art.get("alignment") != "eastern"

        meta_rt = get_source_metadata("https://rt.com/page")
        assert meta_rt.get("alignment") == "eastern"

        meta_sub_rt = get_source_metadata("https://sub.rt.com/page")
        assert meta_sub_rt.get("alignment") == "eastern"


class TestC13NaivePublisherMatching:
    """C13: Publisher matching must use exact match or token-set comparison, not substring containment."""

    def test_publisher_time_does_not_match_new_york_times(self):
        meta_time = get_source_metadata("https://unknown-domain-x.com", publisher="Time")
        assert meta_time.get("name") != "New York Times"

        meta_nyt = get_source_metadata("https://unknown-domain-x.com", publisher="New York Times")
        assert meta_nyt.get("name") == "New York Times"

        meta_nyt_permuted = get_source_metadata("https://unknown-domain-x.com", publisher="York New Times")
        assert meta_nyt_permuted.get("name") == "New York Times"
