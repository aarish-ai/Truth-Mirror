"""Sub-claim decomposition for compound statements."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class DecompositionResult:
    sub_claims: list[str]
    logical_joiners: list[str]
    interpretive_fragments: list[str]
    hidden_premises: list[str]
    temporal_claims: list[str] = field(default_factory=list)
    causal_claims: list[str] = field(default_factory=list)
    conditional_claims: list[str] = field(default_factory=list)
    statistical_claims: list[str] = field(default_factory=list)
    dependencies: list[tuple[str, str, str]] = field(default_factory=list)


INTERPRETIVE_MARKERS = {"terrible", "great", "best", "worst", "disaster", "amazing"}
TEMPORAL_MARKERS = {"before", "after", "during", "when", "while", "since", "until"}
CAUSAL_MARKERS = {"because", "due to", "caused", "leads to", "resulted in", "therefore", "thus", "consequently"}
CONDITIONAL_MARKERS = {"if", "unless", "provided that", "assuming", "whether"}
STATISTICAL_MARKERS = {r"\d+%", r"\d+\s*percent", r"\brate\b", r"\bratio\b", r"\bincrease\b", r"\bdecrease\b", r"\baverage\b"}


def _mock_dependency_parse(text: str) -> list[tuple[str, str, str]]:
    """A lightweight heuristic for extracting basic dependencies (Subject-Verb-Object)."""
    deps = []
    # Very simplistic mock dependency extraction
    words = [w.strip(",.;()[]{}") for w in text.split() if w.strip(",.;()[]{}")]
    if len(words) >= 3:
        # Mock a subject-verb-object relationship
        deps.append((words[1], "nsubj", words[0]))
        deps.append((words[1], "dobj", words[2]))
    return deps


def decompose_claim(claim: str) -> DecompositionResult:
    joiners = re.findall(r"\b(and|or|but|if|unless)\b", claim, flags=re.IGNORECASE)
    parts = re.split(r"\b(?:and|or|but|if|unless)\b", claim, flags=re.IGNORECASE)
    sub_claims = [p.strip(" ,.;") for p in parts if p.strip(" ,.;")]
    
    interpretive_fragments = [
        s for s in sub_claims if any(marker in s.lower() for marker in INTERPRETIVE_MARKERS)
    ]
    
    temporal_claims = [
        s for s in sub_claims if any(marker in s.lower() for marker in TEMPORAL_MARKERS)
    ]
    
    causal_claims = [
        s for s in sub_claims if any(marker in s.lower() for marker in CAUSAL_MARKERS)
    ]
    
    conditional_claims = [
        s for s in sub_claims if any(marker in s.lower() for marker in CONDITIONAL_MARKERS)
    ]
    
    statistical_claims = []
    for s in sub_claims:
        if any(re.search(marker, s, flags=re.IGNORECASE) for marker in STATISTICAL_MARKERS):
            statistical_claims.append(s)
            
    hidden_premises: list[str] = []
    if causal_claims or "caused" in claim.lower():
        hidden_premises.append("Assumes causality and not just correlation.")
    if "quote" in claim.lower():
        hidden_premises.append("Needs exact source transcript for quote verification.")
        
    dependencies = _mock_dependency_parse(claim)

    return DecompositionResult(
        sub_claims=sub_claims or [claim.strip()],
        logical_joiners=[j.lower() for j in joiners],
        interpretive_fragments=interpretive_fragments,
        hidden_premises=hidden_premises,
        temporal_claims=temporal_claims,
        causal_claims=causal_claims,
        conditional_claims=conditional_claims,
        statistical_claims=statistical_claims,
        dependencies=dependencies
    )

