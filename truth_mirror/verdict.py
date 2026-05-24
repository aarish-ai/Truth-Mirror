"""Final verdict aggregation and abstention logic."""

from __future__ import annotations

from collections import Counter

from truth_mirror.abstention import compute_uncertainty
from truth_mirror.models import EvidenceItem, SubClaimResult, VerificationResult


def _status_from_counts(stance_counts: Counter[str], avg_quality: float) -> tuple[str, float]:
    supports = stance_counts.get("supports", 0)
    contradicts = stance_counts.get("contradicts", 0)
    neutral = stance_counts.get("neutral", 0)
    insufficient = stance_counts.get("insufficient", 0)
    total = supports + contradicts + neutral + insufficient
    if total == 0 or insufficient >= max(1, total - 1) or avg_quality < 0.45:
        return "unclear", 0.25
    if supports > 0 and contradicts == 0:
        return "supported", min(0.9, 0.5 + avg_quality * 0.4)
    if contradicts > 0 and supports == 0:
        return "contradicted", min(0.9, 0.5 + avg_quality * 0.4)
    if supports > 0 and contradicts > 0:
        return "partially_supported", 0.55
    if neutral > 0 and supports == 0 and contradicts == 0:
        return "unclear", 0.35
    if neutral > 0:
        return "unsupported", 0.45
    return "unclear", 0.3


def aggregate_verdict(
    original_claim: str,
    normalized_claim: str,
    claim_type: str,
    sub_claim_results: list[SubClaimResult],
    warnings: list[str],
    missing_information: list[str],
) -> VerificationResult:
    if not sub_claim_results:
        return VerificationResult(
            original_claim=original_claim,
            normalized_claim=normalized_claim,
            claim_type=claim_type,
            sub_claims=[],
            final_verdict="Unclear",
            confidence=0.2,
            confidence_interval=(0.0, 0.4),
            evidence_summary="No sub-claims to verify.",
            key_sources=[],
            reasoning="No checkable sub-claims detected. Need a concrete factual claim.",
            missing_information=["Need a concrete factual claim."],
            warnings=warnings + ["insufficient decomposition"],
        )

    status_counts = Counter(s.status for s in sub_claim_results)
    mean_conf = sum(s.confidence for s in sub_claim_results) / len(sub_claim_results)
    mean_lower = sum(s.confidence_interval[0] for s in sub_claim_results) / len(sub_claim_results)
    mean_upper = sum(s.confidence_interval[1] for s in sub_claim_results) / len(sub_claim_results)

    if status_counts["contradicted"] > 0 and status_counts["supported"] == 0:
        verdict = "Contradicted"
    elif status_counts["supported"] == len(sub_claim_results):
        verdict = "Supported"
    elif status_counts["supported"] > 0 or status_counts["contradicted"] > 0:
        verdict = "Partially supported"
    elif status_counts["unsupported"] > 0:
        verdict = "Unsupported"
    else:
        verdict = "Unclear"

    reasoning = (
        f"Evaluated {len(sub_claim_results)} sub-claim(s). "
        f"Claim type route: {claim_type}. "
        "Confidence is based on evidence quality and agreement."
    )
    
    all_evidence = [e for s in sub_claim_results for e in s.evidence]
    key_sources = list({e.url_or_id for e in all_evidence if e.url_or_id})
    if all_evidence:
        evidence_summary = f"Aggregated {len(all_evidence)} pieces of evidence across {len(sub_claim_results)} sub-claims."
    else:
        evidence_summary = "No evidence was found for the sub-claims."

    return VerificationResult(
        original_claim=original_claim,
        normalized_claim=normalized_claim,
        claim_type=claim_type,
        sub_claims=sub_claim_results,
        final_verdict=verdict,
        confidence=round(mean_conf, 3),
        confidence_interval=(round(mean_lower, 3), round(mean_upper, 3)),
        evidence_summary=evidence_summary,
        key_sources=key_sources,
        reasoning=reasoning,
        missing_information=missing_information,
        warnings=warnings,
    )


def build_subclaim_result(text: str, evidence: list[EvidenceItem]) -> SubClaimResult:
    stances = Counter(item.stance for item in evidence)
    if evidence:
        avg_quality = sum((item.relevance_score + item.credibility_score) / 2 for item in evidence) / len(
            evidence
        )
    else:
        avg_quality = 0.0
    status, confidence = _status_from_counts(stances, avg_quality)
    interval, provenance, _ = compute_uncertainty(evidence, confidence)
    
    if interval[1] - interval[0] > 0.6:
        status = "unclear"
        
    return SubClaimResult(
        text=text,
        status=status,
        confidence=round(confidence, 3),
        confidence_interval=(round(interval[0], 3), round(interval[1], 3)),
        provenance=provenance,
        evidence=evidence
    )

