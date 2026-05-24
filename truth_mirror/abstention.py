"""Abstention calibration based on evidence sufficiency and conflict."""

from __future__ import annotations

from collections import Counter

from truth_mirror.models import EvidenceItem


def compute_uncertainty(evidence: list[EvidenceItem], base_confidence: float) -> tuple[tuple[float, float], list[str], list[str]]:
    """Returns confidence interval, provenance transparency, and warnings based on evidence."""
    if not evidence:
        return (0.0, 0.0), ["No sources provided."], ["no-evidence-retrieved"]

    warnings: list[str] = []
    provenance: list[str] = []
    stances = Counter(item.stance for item in evidence)
    total = len(evidence)
    contradict_ratio = stances.get("contradicts", 0) / total
    support_ratio = stances.get("supports", 0) / total
    insufficient_ratio = stances.get("insufficient", 0) / total
    neutral_ratio = stances.get("neutral", 0) / total
    avg_quality = sum((i.relevance_score + i.credibility_score) / 2 for i in evidence) / total
    independence = len({i.independence_key for i in evidence if i.independence_key}) / total

    if independence < 0.3:
        warnings.append("low-source-independence")
        provenance.append("Sources appear highly correlated or lack independent verification.")
    else:
        provenance.append("Good source independence.")

    if avg_quality < 0.3:
        warnings.append("low-evidence-quality")
        provenance.append("Overall evidence quality is low based on relevance and credibility.")
    else:
        provenance.append("Evidence quality is generally acceptable.")

    if insufficient_ratio > 0.7:
        warnings.append("mostly-insufficient-evidence")
        provenance.append(f"High proportion ({insufficient_ratio:.0%}) of evidence is insufficient to verify the claim.")
        
    if support_ratio > 0 and contradict_ratio > 0:
        warnings.append("conflicting-evidence")
        provenance.append("Conflicting sources detected (both supporting and contradicting).")

    # Margin of error based on uncertainty factors
    uncertainty_margin = (
        0.2 * insufficient_ratio
        + 0.1 * neutral_ratio
        + 0.3 * (1 if support_ratio > 0 and contradict_ratio > 0 else 0)
        + 0.2 * (1 - avg_quality)
        + 0.1 * (1 - independence)
    )

    lower_bound = max(0.0, base_confidence - uncertainty_margin)
    upper_bound = min(1.0, base_confidence + uncertainty_margin)
    
    return (lower_bound, upper_bound), provenance, warnings

