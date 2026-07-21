"""Pipeline orchestrator for Truth Mirror MVP."""

from __future__ import annotations

from dataclasses import asdict

from truth_mirror.abstention import compute_uncertainty
from truth_mirror.decomposition import decompose_claim
from truth_mirror.models import VerificationResult
from truth_mirror.normalization import normalize_claim
from truth_mirror.routing import detect_claim_type, get_verifier_class
from truth_mirror.stance import StanceAnalyzer
from truth_mirror.verdict import aggregate_verdict

from truth_mirror.retrieval_free import FreeSourceRetrieval
from truth_mirror.entity_resolution import EntityResolver
from truth_mirror.context_tracker import ContextTracker
from truth_mirror.triangulation import HostileSourceTriangulator
from truth_mirror.temporal_validator import TemporalValidator
from truth_mirror.gemini_analyzer import GeminiAnalyzer
from truth_mirror.kg_verifier import KGVerifier
from truth_mirror.narrative_clusterer import NarrativeClusterer
from truth_mirror.local_decomposer import LocalDecomposer
import json
import os
from truth_mirror.eval_logger import EvalLogger


class TruthMirrorPipeline:
    def __init__(self) -> None:
        self.retriever = FreeSourceRetrieval()
        try:
            from truth_mirror.retrieval_news import GoogleNewsRSSConnector
        except ImportError:
            pass
        self.stance_analyzer = StanceAnalyzer()
        self.entity_resolver = EntityResolver(use_dbpedia=True)
        self.context_tracker = ContextTracker()
        self.triangulator = HostileSourceTriangulator()
        self.temporal_validator = TemporalValidator()
        self.gemini_analyzer = GeminiAnalyzer()
        self.local_decomposer = LocalDecomposer()
        self.kg_verifier = KGVerifier()
        self.narrative_clusterer = NarrativeClusterer()
        self.eval_logger = EvalLogger()
        
        from truth_mirror.geo_query_generator import GeoQueryGenerator
        from truth_mirror.search_planner import SearchPlanner
        self.decomposer = LocalDecomposer()
        self.query_generator = GeoQueryGenerator()
        self.search_planner = SearchPlanner(self.retriever, self.query_generator)

    def verify(self, claim: str, request_id: str = "__global__") -> VerificationResult:
        from truth_mirror.claim_scope_gate import gate_claim, ClaimScopeResult
        from truth_mirror.models import GeopoliticalResult
        
        gate_res = gate_claim(claim)
        if not gate_res.is_in_scope:
            return GeopoliticalResult(
                original_claim=claim,
                is_geopolitical=False,
                rejection_reason=gate_res.rejection_reason
            )
            
        from truth_mirror.geo_orchestrator import GeopoliticalPipeline
        geo_pipeline = GeopoliticalPipeline()
        return geo_pipeline.verify(claim, gate_res, request_id=request_id)

    @staticmethod
    def to_json(result) -> dict:
        """Serialise a VerificationResult or GeopoliticalResult to a dict guaranteed to include all
        frontend-required fields: final_verdict, confidence, reasoning,
        evidence_summary, key_sources, and warnings."""
        from truth_mirror.models import VerificationResult, GeopoliticalResult
        if isinstance(result, GeopoliticalResult):
            return asdict(result)
        base = asdict(result)
        # Ensure every field the frontend expects is present with a sane default.
        required_fields = {
            "final_verdict": base.get("final_verdict", "Unclear"),
            "confidence": base.get("confidence", 0.0),
            "confidence_interval": base.get("confidence_interval", (0.0, 1.0)),
            "reasoning": base.get("reasoning", ""),
            "evidence_summary": base.get("evidence_summary", "No evidence summary available."),
            "key_sources": base.get("key_sources", []),
            "warnings": base.get("warnings", []),
            "missing_information": base.get("missing_information", []),
            "claim_type": base.get("claim_type", ""),
            "original_claim": base.get("original_claim", ""),
            "normalized_claim": base.get("normalized_claim", ""),
            "sub_claims": base.get("sub_claims", []),
            "hidden_story_items": base.get("hidden_story_items", []),
            "evidence_by_region": base.get("evidence_by_region", {}),
            "geo_divergence_detected": base.get("geo_divergence_detected", False),
            "narrative_coherence_score": base.get("narrative_coherence_score", 0.0),
            "source_diversity_score": base.get("source_diversity_score", 0.0),
            "human_review_recommended": base.get("human_review_recommended", False),
            "generated_at": base.get("generated_at", ""),
        }
        # Merge: required_fields takes priority; keep any extra keys from base.
        return {**base, **required_fields}
