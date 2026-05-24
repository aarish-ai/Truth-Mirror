"""Claim normalization and lightweight linguistic parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class NormalizedClaim:
    original: str
    normalized: str
    language: str
    entities: list[str]
    dates: list[str]
    quantities: list[str]
    is_time_sensitive: bool


TIME_WORDS = {"today", "yesterday", "this week", "this month", "breaking", "just now"}


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _detect_language(text: str) -> str:
    # MVP heuristic: default to English unless obvious non-latin heavy text
    latin_chars = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    letters = sum(1 for ch in text if ch.isalpha())
    if letters == 0:
        return "unknown"
    return "en" if latin_chars / letters > 0.7 else "unknown"


def normalize_claim(claim: str) -> NormalizedClaim:
    cleaned = _normalize_spaces(claim)
    lowered = cleaned.lower()
    entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", cleaned)
    dates = re.findall(r"\b(?:\d{4}|\d{1,2}/\d{1,2}/\d{2,4})\b", cleaned)
    quantities = re.findall(r"\b\d+(?:\.\d+)?%?\b", cleaned)
    is_time_sensitive = any(word in lowered for word in TIME_WORDS)
    if re.search(r"\b(today|yesterday)\b", lowered):
        dates.append(datetime.now(timezone.utc).date().isoformat())
    return NormalizedClaim(
        original=claim,
        normalized=cleaned,
        language=_detect_language(cleaned),
        entities=entities,
        dates=dates,
        quantities=quantities,
        is_time_sensitive=is_time_sensitive,
    )

