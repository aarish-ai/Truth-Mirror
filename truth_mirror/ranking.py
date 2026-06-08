"""Evidence ranking by relevance, credibility, recency, and independence."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from truth_mirror.credibility import CredibilityRegistry
from truth_mirror.models import EvidenceItem
from sentence_transformers import SentenceTransformer, util

REGISTRY = CredibilityRegistry.load(
    str(Path(__file__).with_name("credibility_registry.json"))
)

_encoder = None

def get_encoder():
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer
        _encoder = SentenceTransformer("all-MiniLM-L6-v2")
    return _encoder

def _semantic_similarity(a: str, b: str) -> float:
    if not a.strip() or not b.strip():
        return 0.0
    from sentence_transformers import util
    enc = get_encoder()
    emb_a = enc.encode(a, convert_to_tensor=True)
    emb_b = enc.encode(b, convert_to_tensor=True)
    # Clamp between 0 and 1
    return max(0.0, float(util.cos_sim(emb_a, emb_b)[0][0]))


def _recency_score(date_text: str) -> float:
    try:
        dt = datetime.fromisoformat(date_text)
    except ValueError:
        # Non-ISO sources are uncertain; treat as mildly stale.
        return 0.45
    age_days = max((datetime.now() - dt).days, 0)
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.8
    if age_days <= 365:
        return 0.6
    return 0.4


def rank_evidence(claim: str, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    seen_keys: set[str] = set()
    
    # Pre-compute cross verification counts (independent sources per stance)
    stance_counts = {}
    for item in evidence:
        if item.stance in ("supports", "contradicts") and item.independence_key not in seen_keys:
            stance_counts[item.stance] = stance_counts.get(item.stance, 0) + 1
            seen_keys.add(item.independence_key)
            
    seen_keys.clear()
    
    scored_items = []
    for item in evidence:
        relevance_score = _semantic_similarity(claim, f"{item.source_title} {item.excerpt}")
        source_credibility = REGISTRY.score(item)
        recency_weight = _recency_score(item.date)
        
        if item.independence_key in seen_keys:
            independence_penalty = -1.0
        else:
            independence_penalty = 0.0
            seen_keys.add(item.independence_key)
            
        if item.source_type in ("official", "academic"):
            primary_source_bonus = 1.0
        else:
            primary_source_bonus = 0.0
            
        if item.source_type == "academic":
            methodological_rigor = 1.0
        elif item.source_type in ("official", "database"):
            methodological_rigor = 0.8
        elif item.source_type == "journalism":
            methodological_rigor = 0.5
        else:
            methodological_rigor = 0.0
            
        cross_verification_bonus = 0.0
        if item.stance in ("supports", "contradicts") and stance_counts.get(item.stance, 1) > 1:
            cross_verification_bonus = 1.0
            
        item.relevance_score = round(relevance_score, 3)
        item.credibility_score = round(source_credibility, 3)
        
        final_score = (
            relevance_score * 0.25 +
            source_credibility * 0.20 +
            recency_weight * 0.15 +
            independence_penalty * 0.10 +
            primary_source_bonus * 0.15 +
            methodological_rigor * 0.10 +
            cross_verification_bonus * 0.05
        )
        scored_items.append((final_score, item))
        
    return [item for _, item in sorted(scored_items, key=lambda x: x[0], reverse=True)]
