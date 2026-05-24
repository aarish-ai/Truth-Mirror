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


class TruthMirrorPipeline:
    def __init__(self) -> None:
        self.retriever = FreeSourceRetrieval()
        self.stance_analyzer = StanceAnalyzer()
        self.entity_resolver = EntityResolver(use_dbpedia=True)
        self.context_tracker = ContextTracker()
        self.triangulator = HostileSourceTriangulator()

    def verify(self, claim: str) -> VerificationResult:
        warnings: list[str] = []
        missing_info: list[str] = []
        normalized = normalize_claim(claim)
        
        if normalized.language != "en":
            warnings.append("non-english-or-unknown-language")
        if normalized.is_time_sensitive:
            warnings.append("time-sensitive-claim-needs-fresh-sources")

        decomposition = decompose_claim(normalized.normalized)
        claim_type = detect_claim_type(normalized.normalized)
        
        entities = self.entity_resolver.resolve_entities(normalized.normalized)
        context = self.context_tracker.track_claim(normalized.normalized, entities)

        sub_results = []
        verifier_cls = get_verifier_class(claim_type)
        verifier = verifier_cls(self.retriever, self.stance_analyzer)

        for sub_claim in decomposition.sub_claims:
            sub_result = verifier.verify_subclaim(sub_claim, context={"context": context, "entities": entities})
            ranked = sub_result.evidence
            
            supporting_sources = [e.url_or_id for e in ranked if e.stance == "supports" and e.url_or_id]
            contradicting_sources = [e.url_or_id for e in ranked if e.stance == "contradicts" and e.url_or_id]
            
            is_hc, t_score, t_reason = self.triangulator.triangulate(sub_claim, supporting_sources, contradicting_sources)
            sub_result.provenance.append(f"Triangulation: {t_reason}")
            
            _, _, abstain_warnings = compute_uncertainty(ranked, sub_result.confidence)
            warnings.extend(f"{sub_claim}: {w}" for w in abstain_warnings)
            
            if not ranked:
                missing_info.append(f"No evidence retrieved for: {sub_claim}")
            
            sub_results.append(sub_result)

        if decomposition.interpretive_fragments:
            warnings.append("contains-opinionated-language")
        warnings.extend(
            "hidden-premise: " + premise for premise in decomposition.hidden_premises
        )
        
        result = aggregate_verdict(
            original_claim=claim,
            normalized_claim=normalized.normalized,
            claim_type=claim_type,
            sub_claim_results=sub_results,
            warnings=warnings,
            missing_information=missing_info,
        )
        result.context = context
        return result

    @staticmethod
    def to_json(result: VerificationResult) -> dict:
        return asdict(result)
