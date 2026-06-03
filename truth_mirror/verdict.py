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
    geo_divergence_detected: bool = False,
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

    if geo_divergence_detected:
        verdict = "Disputed (geo-narrative divergence)"
        mean_conf = min(mean_conf, 0.7)
        mean_lower = min(mean_lower, 0.7)
        mean_upper = min(mean_upper, 0.7)

    reasoning = (
        f"Evaluated {len(sub_claim_results)} sub-claim(s). "
        f"Claim type route: {claim_type}. "
        "Confidence is based on evidence quality and agreement."
    )

    all_evidence = [e for s in sub_claim_results for e in s.evidence]
    key_sources = list({e.url_or_id for e in all_evidence if e.url_or_id})

    # ── Build a detailed, journalistic evidence_summary ───────────────────────
    if all_evidence:
        summary_lines: list[str] = [
            f"Analysis of {len(sub_claim_results)} sub-claim(s) yielded "
            f"{len(all_evidence)} evidence item(s). "
            f"Overall verdict: {verdict}.\n"
        ]

        for sc in sub_claim_results:
            if not sc.evidence:
                summary_lines.append(
                    f"• Sub-claim '{sc.text}': No evidence retrieved "
                    f"(status: {sc.status})."
                )
                continue

            # Group evidence by stance for this sub-claim
            supporting = [e for e in sc.evidence if e.stance == "supports"]
            contradicting = [e for e in sc.evidence if e.stance == "contradicts"]
            neutral = [e for e in sc.evidence if e.stance not in ("supports", "contradicts")]

            summary_lines.append(
                f"• Sub-claim '{sc.text}' — status: {sc.status}, "
                f"confidence: {sc.confidence:.0%}."
            )

            for ev in supporting[:3]:
                title = ev.source_title or ev.publisher or ev.url_or_id or "Unknown"
                excerpt = (ev.excerpt or "").strip()[:200]
                summary_lines.append(
                    f"    ✅ SUPPORTS — [{title}] ({ev.publisher}): "
                    f"{excerpt}{'…' if len(ev.excerpt or '') > 200 else ''}"
                )

            for ev in contradicting[:3]:
                title = ev.source_title or ev.publisher or ev.url_or_id or "Unknown"
                excerpt = (ev.excerpt or "").strip()[:200]
                summary_lines.append(
                    f"    ❌ CONTRADICTS — [{title}] ({ev.publisher}): "
                    f"{excerpt}{'…' if len(ev.excerpt or '') > 200 else ''}"
                )

            for ev in neutral[:2]:
                title = ev.source_title or ev.publisher or ev.url_or_id or "Unknown"
                excerpt = (ev.excerpt or "").strip()[:150]
                if excerpt:
                    summary_lines.append(
                        f"    ℹ️ NEUTRAL — [{title}] ({ev.publisher}): "
                        f"{excerpt}{'…' if len(ev.excerpt or '') > 150 else ''}"
                    )

        # Verdict rationale
        status_counts = Counter(s.status for s in sub_claim_results)
        summary_lines.append(
            f"\nVerdict rationale: "
            f"{status_counts.get('supported', 0)} sub-claim(s) supported, "
            f"{status_counts.get('contradicted', 0)} contradicted, "
            f"{status_counts.get('partially_supported', 0)} partially supported, "
            f"{status_counts.get('unclear', 0)} unclear. "
            f"This produced a final verdict of '{verdict}' at "
            f"{mean_conf:.0%} confidence."
        )

        evidence_summary = "\n".join(summary_lines)
    else:
        evidence_summary = (
            "No evidence was retrieved for any of the sub-claims. "
            "The claim could not be verified with available sources."
        )

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
        geo_divergence_detected=geo_divergence_detected,
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

