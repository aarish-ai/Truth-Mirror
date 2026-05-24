"""Stance analysis with optional NLI model and robust fallback."""

from __future__ import annotations

import re

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
                    task="zero-shot-classification",
                    model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
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
        if self._clf is None:
            return self._fallback(claim, evidence_text)
        try:
            labels = ["supports", "contradicts", "neutral"]
            result = self._clf(
                sequences=f"Claim: {claim}\nEvidence: {evidence_text}",
                candidate_labels=labels,
                multi_label=False,
            )
            top_label = str(result["labels"][0]).lower()
            top_score = float(result["scores"][0])
            if top_score < 0.52:
                return "insufficient"
            return top_label if top_label in labels else "neutral"
        except Exception:
            return self._fallback(claim, evidence_text)

