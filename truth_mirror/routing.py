"""Claim type routing for strategy selection."""

from __future__ import annotations

import re
from typing import Type

from truth_mirror.verifiers import (
    BaseVerifier,
    DefaultVerifier,
    EventVerifier,
    PolicyVerifier,
    QuoteVerifier,
    ScientificVerifier,
    StatisticalVerifier,
)


def detect_claim_type(claim: str) -> str:
    """Detect the logical type of the claim."""
    text = claim.lower()
    if any(k in text for k in ("today", "breaking", "yesterday", "this week")):
        return "breaking news / recent event"
    if any(k in text for k in ("according to", "said", "quote", "stated")):
        return "quote attribution"
    if re.search(r"\b\d+(?:\.\d+)?%|\b\d+(?:,\d{3})+\b", text):
        return "statistic / numeric claim"
    if any(k in text for k in ("law", "bill", "court", "policy", "regulation")):
        return "policy / legal claim"
    if any(k in text for k in ("study", "clinical", "vaccine", "disease", "medical")):
        return "scientific / medical claim"
    if any(k in text for k in ("think", "best", "worst", "terrible", "good")):
        return "opinion dressed as fact"
    if re.search(r"\b(in \d{4}|century|historical|history)\b", text):
        return "historical fact"
    return "mixed or ambiguous claim"


def get_verifier_class(claim_type: str) -> Type[BaseVerifier]:
    """Route a claim type to the appropriate verifier class."""
    routing_table = {
        "breaking news / recent event": EventVerifier,
        "historical fact": EventVerifier,
        "quote attribution": QuoteVerifier,
        "statistic / numeric claim": StatisticalVerifier,
        "policy / legal claim": PolicyVerifier,
        "scientific / medical claim": ScientificVerifier,
        "opinion dressed as fact": DefaultVerifier,
        "mixed or ambiguous claim": DefaultVerifier,
    }
    return routing_table.get(claim_type, DefaultVerifier)

def get_verifier_for_claim(claim: str) -> Type[BaseVerifier]:
    """Detect claim type and return the appropriate verifier class."""
    return get_verifier_class(detect_claim_type(claim))

