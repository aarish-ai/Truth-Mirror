"""Specific verification strategies for different types of claims."""

from __future__ import annotations

from truth_mirror.models import SubClaimResult, EvidenceItem
from truth_mirror.retrieval import EvidenceRetriever
from truth_mirror.stance import StanceAnalyzer
from truth_mirror.ranking import rank_evidence
from truth_mirror.verdict import build_subclaim_result

class BaseVerifier:
    """Base class for all claim verifiers."""
    
    def __init__(self, retriever: EvidenceRetriever, stance_analyzer: StanceAnalyzer):
        self.retriever = retriever
        self.stance_analyzer = stance_analyzer

    def verify_subclaim(self, subclaim: str, context: dict = None) -> SubClaimResult:
        """Verify a single subclaim. Overridden by specific verifiers if needed."""
        evidence = self.retriever.retrieve(subclaim)
        ranked = rank_evidence(subclaim, evidence)[:4]
        for item in ranked:
            item.stance = self.stance_analyzer.detect(subclaim, item)
        return build_subclaim_result(subclaim, ranked)


class StatisticalVerifier(BaseVerifier):
    """Verifier optimized for numerical and statistical claims."""
    # Could potentially use specialized query generation or filtering.
    pass


class EventVerifier(BaseVerifier):
    """Verifier optimized for breaking news or historical events."""
    pass


class QuoteVerifier(BaseVerifier):
    """Verifier optimized for quotes and attributions."""
    pass


class PolicyVerifier(BaseVerifier):
    """Verifier optimized for policy and legal claims."""
    pass


class ScientificVerifier(BaseVerifier):
    """Verifier optimized for scientific and medical claims."""
    pass


class DefaultVerifier(BaseVerifier):
    """Fallback verifier for mixed or ambiguous claims."""
    pass
