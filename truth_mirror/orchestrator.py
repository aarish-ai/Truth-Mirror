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
from truth_mirror.agent import ReActAgent
from truth_mirror.llm_client import LLMClient
import json


class TruthMirrorPipeline:
    def __init__(self) -> None:
        self.retriever = FreeSourceRetrieval()
        self.stance_analyzer = StanceAnalyzer()
        self.entity_resolver = EntityResolver(use_dbpedia=True)
        self.context_tracker = ContextTracker()
        self.triangulator = HostileSourceTriangulator()
        self.temporal_validator = TemporalValidator()
        self.gemini_analyzer = GeminiAnalyzer()
        self.llm_client = LLMClient()

    def verify(self, claim: str) -> VerificationResult:
        warnings: list[str] = []
        missing_info: list[str] = []
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

        claim_type = detect_claim_type(normalized.normalized)
        entities = self.entity_resolver.resolve_entities(normalized.normalized)
        context = self.context_tracker.track_claim(normalized.normalized, entities)

        sub_results = []
        
        def tool_decompose(q: str) -> str:
            """Decompose the claim into subclaims."""
            dec = decompose_claim(q)
            if dec.interpretive_fragments:
                warnings.append("contains-opinionated-language")
            warnings.extend("hidden-premise: " + p for p in dec.hidden_premises)
            return json.dumps(dec.sub_claims)

        def tool_verify_subclaim(subclaim: str) -> str:
            """Verify a single subclaim and return a summary."""
            verifier_cls = get_verifier_class(claim_type)
            verifier = verifier_cls(self.retriever, self.stance_analyzer)
            sr = verifier.verify_subclaim(subclaim, context={"context": context, "entities": entities, "claim_type": claim_type})
            
            supporting = [e.url_or_id for e in sr.evidence if e.stance == "supports" and e.url_or_id]
            contradicting = [e.url_or_id for e in sr.evidence if e.stance == "contradicts" and e.url_or_id]
            
            is_hc, t_score, t_reason = self.triangulator.triangulate(subclaim, supporting, contradicting)
            sr.provenance.append(f"Triangulation: {t_reason}")
            
            _, _, abstain_warnings = compute_uncertainty(sr.evidence, sr.confidence)
            warnings.extend(f"{subclaim}: {w}" for w in abstain_warnings)
            
            if not sr.evidence:
                missing_info.append(f"No evidence retrieved for: {subclaim}")
                
            sub_results.append(sr)
            return f"Status: {sr.status}, Confidence: {sr.confidence}. Sources: {len(sr.evidence)}."

        tools = {
            "decompose_claim": tool_decompose,
            "verify_subclaim": tool_verify_subclaim
        }
        
        agent = ReActAgent(self.llm_client, tools)
        react_answer = agent.run(claim)

        all_evidence = []
        for sr in sub_results:
            all_evidence.extend(sr.evidence)
            
        if not sub_results:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Agent failed to use tools. Falling back to linear verification.")
            try:
                subclaims_json = tool_decompose(claim)
                for sc in json.loads(subclaims_json):
                    tool_verify_subclaim(sc)
                for sr in sub_results:
                    all_evidence.extend(sr.evidence)
            except Exception as e:
                logger.error(f"Linear fallback failed: {e}")
            
        gemini_result = self.gemini_analyzer.synthesize(
            claim, all_evidence
        )

        result = aggregate_verdict(
            original_claim=claim,
            normalized_claim=normalized.normalized,
            claim_type=claim_type,
            sub_claim_results=sub_results,
            warnings=warnings,
            missing_information=missing_info,
        )
        
        if gemini_result:
            result.final_verdict = gemini_result["verdict"]
            result.reasoning = f"Gemini Synthesis: {gemini_result['reasoning']}\nReAct Agent reasoning: {react_answer}"
        else:
            result.reasoning = f"ReAct Agent reasoning: {react_answer}"

        result.context = context
        result.narrative_coherence_score = getattr(context, "narrative_coherence_score", 1.0)
        self.context_tracker.record_verdict(normalized.normalized, result.final_verdict)
        return result

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
