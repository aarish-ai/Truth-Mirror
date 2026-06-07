"""Specific verification strategies for different types of claims."""

from __future__ import annotations

from truth_mirror.models import SubClaimResult, EvidenceItem
from truth_mirror.retrieval import EvidenceRetriever
from truth_mirror.stance import StanceAnalyzer
from truth_mirror.ranking import rank_evidence
from truth_mirror.verdict import build_subclaim_result
from truth_mirror.retrieval_archival import WaybackMachineConnector
from truth_mirror.normalization import inject_temporal_context

class BaseVerifier:
    """Base class for all claim verifiers."""
    
    def __init__(self, retriever: EvidenceRetriever, stance_analyzer: StanceAnalyzer):
        self.retriever = retriever
        self.stance_analyzer = stance_analyzer
        self.wayback = WaybackMachineConnector()

    def verify_subclaim(self, subclaim: str, context: dict = None) -> SubClaimResult:
        """Verify a single subclaim. Overridden by specific verifiers if needed."""
        claim_type = (context or {}).get("claim_type", "mixed or ambiguous claim")
        
        enriched_subclaim, _ = inject_temporal_context(subclaim)
        evidence = self.retriever.retrieve(enriched_subclaim, claim_type=claim_type)

        # Hidden Story retrieval pass targeting dissenting/minority sources
        negated_claim = f"not {enriched_subclaim}"
        hidden_evidence = self.retriever.retrieve(negated_claim, claim_type=claim_type)
        for item in hidden_evidence:
            item.is_hidden_story = True
            if item.url_or_id and item.url_or_id.startswith("http"):
                wb = self.wayback.get_archived_url(item.url_or_id)
                if wb and "url" in wb:
                    item.url_or_id = wb["url"]
                    item.source_title = f"[Archived] {item.source_title}"

        evidence.extend(hidden_evidence)

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
