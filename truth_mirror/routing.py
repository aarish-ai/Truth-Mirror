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

# Claim types that should prioritise news/Wikipedia sources over academic ones.
NEWS_FIRST_CLAIM_TYPES = {
    "biographical",
    "political",
    "current_event",
    "breaking news / recent event",
    "geopolitical",
}


def detect_claim_type(claim: str) -> str:
    """Detect the logical type of the claim.

    Returns one of:
        biographical, political, current_event,
        breaking news / recent event, quote attribution,
        statistic / numeric claim, policy / legal claim,
        scientific / medical claim, opinion dressed as fact,
        historical fact, mixed or ambiguous claim
    """
    text = claim.lower()

    # ── Biographical: people's life/death/age/role status ────────────────────
    if re.search(
        r"\b(born|died|death|alive|dead|age|biography|nationality|married|divorced"
        r"|spouse|parent|child|founded|created|invented|president of|prime minister of"
        r"|ceo of|leader of|served as|was a|is a)\b",
        text,
    ):
        return "biographical"

    # ── Political: elections, governments, parties, leaders ──────────────────
    if re.search(
        r"\b(election|elected|vote|senator|congress|parliament|president|prime minister"
        r"|governor|mayor|minister|administration|party|campaign|inauguration|impeach"
        r"|referendum|ballot|democrat|republican|geopolitical|sanction|treaty|diplomat)\b",
        text,
    ):
        return "political"

    # ── Current/recent events ─────────────────────────────────────────────────
    if any(
        k in text
        for k in (
            "today",
            "breaking",
            "yesterday",
            "this week",
            "this month",
            "this year",
            "recently",
            "latest",
            "ongoing",
            "current",
        )
    ):
        return "current_event"

    # ── Legacy "breaking news / recent event" (kept for backward compat) ─────
    # (covered above; left as dead code path but harmless)

    # ── Quote attribution ────────────────────────────────────────────────────
    if any(k in text for k in ("according to", "said", "quote", "stated")):
        return "quote attribution"

    # ── Statistic / numeric claim ────────────────────────────────────────────
    if re.search(r"\b\d+(?:\.\d+)?%|\b\d+(?:,\d{3})+\b", text):
        return "statistic / numeric claim"

    # ── Policy / legal claim ─────────────────────────────────────────────────
    if any(k in text for k in ("law", "bill", "court", "policy", "regulation")):
        return "policy / legal claim"

    # ── Scientific / medical claim ────────────────────────────────────────────
    if any(k in text for k in ("study", "clinical", "vaccine", "disease", "medical")):
        return "scientific / medical claim"

    # ── Opinion dressed as fact ──────────────────────────────────────────────
    if any(k in text for k in ("think", "best", "worst", "terrible", "good")):
        return "opinion dressed as fact"

    # ── Historical fact ───────────────────────────────────────────────────────
    if re.search(r"\b(in \d{4}|century|historical|history)\b", text):
        return "historical fact"

    return "mixed or ambiguous claim"


def get_verifier_class(claim_type: str) -> Type[BaseVerifier]:
    """Route a claim type to the appropriate verifier class."""
    routing_table = {
        "biographical": EventVerifier,
        "political": EventVerifier,
        "current_event": EventVerifier,
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
