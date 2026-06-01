"""Core data models for Truth Mirror."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

SubClaimStatus = Literal[
    "supported",
    "partially_supported",
    "contradicted",
    "unsupported",
    "unclear",
]
Stance = Literal["supports", "contradicts", "neutral", "insufficient"]
SourceType = Literal["official", "journalism", "academic", "database", "other"]
VerdictLabel = Literal[
    "Supported",
    "Partially supported",
    "Contradicted",
    "Unsupported",
    "Unclear",
    "Disputed (geo-narrative divergence)",
]


@dataclass(slots=True)
class EvidenceItem:
    source_title: str
    source_type: SourceType
    publisher: str
    date: str
    url_or_id: str
    excerpt: str
    language: str = "en"
    author: str = "unknown"
    retrieval_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    relevance_score: float = 0.0
    credibility_score: float = 0.0
    independence_key: str = ""
    stance: Stance = "insufficient"
    perspective_label: str = "unknown"
    is_hidden_story: bool = False


@dataclass(slots=True)
class SubClaimResult:
    text: str
    status: SubClaimStatus
    confidence: float
    confidence_interval: tuple[float, float]
    provenance: list[str]
    evidence: list[EvidenceItem]


@dataclass(slots=True)
class Entity:
    name: str
    uri: str
    types: list[str] = field(default_factory=list)
    description: str = ""
    score: float = 0.0


@dataclass(slots=True)
class ClaimContext:
    entities: list[Entity] = field(default_factory=list)
    previous_claims: list[str] = field(default_factory=list)
    background_summary: str = ""
    narrative_coherence_score: float = 1.0



@dataclass(slots=True)
class VerificationResult:
    original_claim: str
    normalized_claim: str
    claim_type: str
    sub_claims: list[SubClaimResult]
    final_verdict: VerdictLabel
    confidence: float
    confidence_interval: tuple[float, float]
    evidence_summary: str
    key_sources: list[str]
    reasoning: str
    missing_information: list[str]
    warnings: list[str]
    context: ClaimContext = field(default_factory=ClaimContext)
    narrative_perspectives: dict[str, str] = field(default_factory=dict)
    geo_divergence_detected: bool = False
    evidence_by_region: dict[str, list[EvidenceItem]] = field(default_factory=dict)
    hidden_story_items: list[EvidenceItem] = field(default_factory=list)
    narrative_coherence_score: float = 0.0
    source_diversity_score: float = 0.0
    human_review_recommended: bool = False
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
