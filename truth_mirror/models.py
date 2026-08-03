"""Core data models for Truth Mirror."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    archive_url: str = ""


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


@dataclass(slots=True)
class GeoActor:
    name: str
    role: str
    stated_position: str

@dataclass(slots=True)
class GeoNarrative:
    bloc: str
    claim: str
    evidence_strength: str  # strong|moderate|weak
    key_evidence: list[str]
    known_bias: str

@dataclass(slots=True)
class GeoStory:
    headline: str
    background: str
    current_situation: str
    key_actors: list[GeoActor]
    timeline_hints: list[str]
    sources_agreeing_on: str

@dataclass(slots=True)
class GeoDisputeAnalysis:
    undisputed_facts: list[str]
    contested_claims: list[str]
    narratives: list[GeoNarrative]
    most_likely_ground_truth: str
    ground_truth_confidence: str  # high|medium|low
    ground_truth_reasoning: str

@dataclass(slots=True)
class GeopoliticalResult:
    claim: str = ""
    original_claim: str = ""
    is_geopolitical: bool = True
    rejection_reason: str = ""
    
    source_analyses: list = field(default_factory=list)
    total_sources: int = 0
    
    perspective_groups: list = field(default_factory=list)
    
    consensus_points: list = field(default_factory=list)
    disputed_points: list = field(default_factory=list)
    
    hidden_stories: list = field(default_factory=list)
    
    verdict_data: dict = field(default_factory=dict)
    
    background: str = ""
    current_situation: str = ""
    verdict: str = "Unclear"
    final_verdict: str = "Unclear"
    confidence: float = 0.0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    temporal_type: str = ""
    temporal_qualifier: str = ""

    def to_json(self) -> dict:
        d = asdict(self)
        d["final_verdict"] = self.verdict
        return d
