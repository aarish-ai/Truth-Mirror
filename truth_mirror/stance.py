"""Stance analysis with Gemini model and robust fallback."""

from __future__ import annotations

import math
import re
import json
import urllib.request
import urllib.error
import time
import logging
from collections import Counter

from truth_mirror.models import EvidenceItem
from truth_mirror.key_rotator import get_current_key, rotate_gemini_key

logger = logging.getLogger(__name__)

NEGATION_TERMS = {"not", "false", "hoax", "denied", "incorrect", "no evidence"}
CONTRAST_TERMS = {"however", "but", "although", "yet"}


class StanceAnalyzer:
    def __init__(self) -> None:
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
            
        prompt = f"""You are an expert fact-checking assistant. Analyze the relationship between the claim and the provided evidence.
Claim: "{claim}"
Evidence: "{evidence_text}"

Determine if the evidence supports the claim, contradicts the claim, is neutral, or if there is insufficient evidence to determine.
Respond strictly in JSON format with a single key "stance" whose value must be one of: "supports", "contradicts", "neutral", "insufficient".
Do not include any explanation or additional text.
"""
        max_attempts = 3
        parsed = None
        for attempt in range(max_attempts):
            api_key = get_current_key()
            if not api_key:
                rotate_gemini_key()
                api_key = get_current_key()
                if not api_key:
                    break

            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            gemini_payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json"
                }
            }
            try:
                req_data = json.dumps(gemini_payload).encode("utf-8")
                req = urllib.request.Request(gemini_url, data=req_data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(content)
                    break
            except urllib.error.HTTPError as e:
                if e.code in (429, 403):
                    wait_time = (2 ** attempt) + 1
                    logger.warning(f"[StanceAnalyzer] Rate limited/forbidden ({e.code}). Rotating key and retrying in {wait_time}s.")
                    rotate_gemini_key()
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"[StanceAnalyzer] HTTPError {e.code}: {e.reason}")
                    break
            except Exception as e:
                logger.warning(f"[StanceAnalyzer] Exception in detect: {e}")
                break

        if parsed and isinstance(parsed, dict) and "stance" in parsed:
            stance = parsed["stance"].strip().lower()
            if stance in ("supports", "contradicts", "neutral", "insufficient"):
                return stance

        return self._fallback(claim, evidence_text)
