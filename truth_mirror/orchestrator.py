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
        
        from truth_mirror.query_generator import QueryGenerator
        from truth_mirror.search_planner import SearchPlanner
        self.query_generator = QueryGenerator()
        self.search_planner = SearchPlanner(self.retriever, self.query_generator)

    def verify(self, claim: str) -> VerificationResult:
        warnings: list[str] = []
        missing_info: list[str] = []
        sub_results = []
        all_evidence = []
        
        GeminiAnalyzer.reset_call_count()
        
        normalized = normalize_claim(claim)
        
        is_valid, temp_reason = self.temporal_validator.validate(normalized.normalized)
        if not is_valid:
            return VerificationResult(
                original_claim=claim,
                normalized_claim=normalized.normalized,
                claim_type="unknown",
                sub_claims=[],
                final_verdict="Contradicted",
                confidence=1.0,
                confidence_interval=(1.0, 1.0),
                evidence_summary="Rejected before retrieval due to temporal impossibility.",
                key_sources=[],
                reasoning=temp_reason,
                missing_information=[],
                warnings=[f"temporal-validation-failed: {temp_reason}"]
            )

        if normalized.language != "en":
            warnings.append("non-english-or-unknown-language")
        if normalized.is_time_sensitive:
            warnings.append("time-sensitive-claim-needs-fresh-sources")

        try:
            entities = self.entity_resolver.resolve_entities(normalized.normalized)
        except Exception as e:
            entities = []
            warnings.append(f"entity-resolution-failed: {str(e)}")

        try:
            context = self.context_tracker.track_claim(normalized.normalized, entities)
        except Exception as e:
            from truth_mirror.models import ClaimContext
            context = ClaimContext()
            warnings.append(f"context-tracking-failed: {str(e)}")
            
        if getattr(context, "background_summary", None):
            warnings.append(f"context-warning: {context.background_summary}")

        dec = decompose_claim(normalized.normalized)
        if dec.interpretive_fragments:
            warnings.append("contains-opinionated-language")
        warnings.extend("hidden-premise: " + p for p in dec.hidden_premises)

        if os.getenv("ENABLE_OLLAMA_DECOMPOSITION", "true").lower() == "true":
            raw_sub_claims = self.local_decomposer.decompose(normalized.normalized)
        else:
            raw_sub_claims = dec.sub_claims

        claim_type = detect_claim_type(normalized.normalized)
        
        for subclaim in raw_sub_claims:
            from truth_mirror.normalization import inject_temporal_context
            from truth_mirror.ranking import rank_evidence
            from truth_mirror.verdict import build_subclaim_result
            
            enriched_subclaim, has_date = inject_temporal_context(subclaim)
            evidence_items, queries_used = self.search_planner.retrieve_for_subclaim(
                enriched_subclaim, claim_type, has_date
            )
            
            ranked = rank_evidence(enriched_subclaim, evidence_items)[:4]
            for item in ranked:
                item.stance = self.stance_analyzer.detect(subclaim, item)
            
            sr = build_subclaim_result(subclaim, ranked)
            sr.provenance.append(f"Queries used: {queries_used}")
            
            is_hc, t_score, t_reason = self.triangulator.triangulate(subclaim, sr.evidence)
            sr.provenance.append(f"Triangulation: {t_reason}")
            
            _, _, abstain_warnings = compute_uncertainty(sr.evidence, sr.confidence)
            warnings.extend(f"{subclaim}: {w}" for w in abstain_warnings)
            
            if not sr.evidence:
                missing_info.append(f"No evidence retrieved for: {subclaim}")
                
            sub_results.append(sr)
            all_evidence.extend(sr.evidence)

        if os.getenv("ENABLE_KG_VERIFICATION", "true").lower() == "true":
            kg_item = self.kg_verifier.verify_claim(normalized.normalized)
            if kg_item:
                all_evidence.append(kg_item)

        heuristic_result = aggregate_verdict(
            original_claim=claim,
            normalized_claim=normalized.normalized,
            claim_type=claim_type,
            sub_claim_results=sub_results,
            warnings=warnings,
            missing_information=missing_info,
        )

        if os.getenv("ENABLE_NARRATIVE_CLUSTERING", "false").lower() == "true":
            cluster_res = self.narrative_clusterer.cluster_and_detect_divergence(claim, all_evidence)
            if cluster_res:
                heuristic_result.geo_divergence_detected = cluster_res.get("divergence_detected", False)
                if heuristic_result.geo_divergence_detected:
                    heuristic_result.warnings.append(cluster_res.get("divergence_summary", ""))

        gemini_result = self.gemini_analyzer.synthesize(claim, all_evidence)
        if gemini_result:
            heuristic_result.final_verdict = gemini_result.get("verdict", heuristic_result.final_verdict)
            heuristic_result.reasoning = f"Gemini Synthesis: {gemini_result.get('reasoning', '')}"
            if "confidence" in gemini_result:
                heuristic_result.confidence = gemini_result["confidence"]
            if "evidence_summary" in gemini_result:
                heuristic_result.evidence_summary = gemini_result["evidence_summary"]

        heuristic_result.context = context
        heuristic_result.narrative_coherence_score = getattr(context, "narrative_coherence_score", 1.0)
        self.context_tracker.record_verdict(normalized.normalized, heuristic_result.final_verdict)
        
        # Log the component-level output
        self.eval_logger.log_run(
            original_query=claim,
            decomposed_claims=raw_sub_claims,
            context=context,
            entities=entities,
            sub_results=sub_results,
            gemini_result=gemini_result,
            final_verdict=heuristic_result.final_verdict
        )
        
        return heuristic_result

    @staticmethod
    def to_json(result: VerificationResult) -> dict:
        """Serialise a VerificationResult to a dict guaranteed to include all
        frontend-required fields: final_verdict, confidence, reasoning,
        evidence_summary, key_sources, and warnings."""
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
