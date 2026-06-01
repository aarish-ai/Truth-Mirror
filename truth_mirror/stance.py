"""Stance analysis with optional NLI model and robust fallback."""

from __future__ import annotations

import math
import re
from collections import Counter

from truth_mirror.models import EvidenceItem


NEGATION_TERMS = {"not", "false", "hoax", "denied", "incorrect", "no evidence"}
CONTRAST_TERMS = {"however", "but", "although", "yet"}

try:
    from transformers import pipeline  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pipeline = None


class StanceAnalyzer:
    def __init__(self) -> None:
        self._clf = None
        if pipeline is not None:
            try:
                # If available locally, this improves over lexical matching.
                self._clf = pipeline(
                    task="text-classification",
                    model="cross-encoder/nli-deberta-v3-large",
                    top_k=None,
                )
            except Exception:
                self._clf = None

    @staticmethod
    def _token_overlap(claim: str, evidence_text: str) -> float:
        claim_tokens = {t for t in re.findall(r"[a-zA-Z0-9]+", claim.lower()) if len(t) > 2}
        ev_tokens = {t for t in re.findall(r"[a-zA-Z0-9]+", evidence_text.lower()) if len(t) > 2}
        if not claim_tokens or not ev_tokens:
            return 0.0
        return len(claim_tokens & ev_tokens) / len(claim_tokens | ev_tokens)

    @staticmethod
    def _cosine_similarity(text1: str, text2: str) -> float:
        t1 = [t for t in re.findall(r"[a-zA-Z0-9]+", text1.lower()) if len(t) > 2]
        t2 = [t for t in re.findall(r"[a-zA-Z0-9]+", text2.lower()) if len(t) > 2]
        c1 = Counter(t1)
        c2 = Counter(t2)
        terms = set(c1) | set(c2)
        dot = sum(c1.get(k, 0) * c2.get(k, 0) for k in terms)
        mag1 = math.sqrt(sum(c1.get(k, 0)**2 for k in terms))
        mag2 = math.sqrt(sum(c2.get(k, 0)**2 for k in terms))
        if not mag1 or not mag2:
            return 0.0
        return dot / (mag1 * mag2)

    def _fallback(self, claim: str, evidence_text: str) -> str:
        overlap = self._token_overlap(claim, evidence_text)
        if overlap < 0.12:
            return "insufficient"
        claim_has_neg = any(t in claim.lower() for t in NEGATION_TERMS)
        ev_has_neg = any(t in evidence_text for t in NEGATION_TERMS)
        has_contrast = any(term in evidence_text for term in CONTRAST_TERMS)
        if claim_has_neg != ev_has_neg and overlap > 0.18:
            return "contradicts"
        if overlap > 0.22 and not has_contrast:
            return "supports"
        return "neutral"

    def detect(self, claim: str, evidence: EvidenceItem) -> str:
        evidence_text = f"{evidence.source_title}. {evidence.excerpt}".strip()
        if len(evidence_text) < 30:
            return "insufficient"
            
        sim = self._cosine_similarity(claim, evidence_text)
        if sim < 0.25:
            return "insufficient"
            
        if self._clf is None:
            return self._fallback(claim, evidence_text)
        try:
            claim_has_neg = any(t in claim.lower() for t in NEGATION_TERMS)
            ev_has_neg = any(t in evidence_text.lower() for t in NEGATION_TERMS)
            
            result = self._clf({"text": claim, "text_pair": evidence_text})
            
            if isinstance(result, list) and isinstance(result[0], list):
                scores = {item['label'].lower(): item['score'] for item in result[0]}
            elif isinstance(result, list) and isinstance(result[0], dict):
                scores = {item['label'].lower(): item['score'] for item in result}
            else:
                return self._fallback(claim, evidence_text)
                
            contradicts_score = scores.get('contradiction', 0.0)
            supports_score = scores.get('entailment', 0.0)
            neutral_score = scores.get('neutral', 0.0)
            
            if not claim_has_neg and ev_has_neg:
                contradicts_score += 0.15
                
            labels_scores = {
                "contradicts": contradicts_score,
                "supports": supports_score,
                "neutral": neutral_score
            }
            top_label = max(labels_scores, key=labels_scores.get)
            top_score = labels_scores[top_label]
            
            if top_score < 0.52:
                return "insufficient"
            return top_label
        except Exception:
            return self._fallback(claim, evidence_text)

