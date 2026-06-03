"""Sub-claim decomposition for compound statements."""

from __future__ import annotations

import re
import json
import os
import logging
from dataclasses import dataclass, field

try:
    from google import genai
    from google.genai import types as genai_types
    from dotenv import load_dotenv
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

logger = logging.getLogger(__name__)


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


def _decompose_claim_regex(claim: str) -> DecompositionResult:
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


def decompose_claim(claim: str) -> DecompositionResult:
    # Short-circuit: if the claim is simple (one subject, one predicate), don't split
    words = claim.strip().split()
    if len(words) <= 10 and not any(kw in claim.lower() for kw in [' and ', ' but ', ' while ', ' also ', ' both ']):
        return DecompositionResult(
            sub_claims=[claim],
            logical_joiners=[],
            interpretive_fragments=[],
            hidden_premises=[]
        )

    if LLM_AVAILABLE:
        try:
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                client = genai.Client(api_key=api_key)
                
                prompt = f"""
You are an expert at breaking down complex claims into verifiable sub-claims. 
Decompose the following claim into its constituent parts.

Claim: "{claim}"

Respond ONLY with a valid JSON object matching this schema. Ensure dependencies is a list of [string, string, string] lists:
{{
  "sub_claims": ["claim 1", "claim 2"],
  "logical_joiners": ["and", "or"],
  "interpretive_fragments": ["fragment 1"],
  "hidden_premises": ["premise 1"],
  "temporal_claims": [],
  "causal_claims": [],
  "conditional_claims": [],
  "statistical_claims": [],
  "dependencies": [["word1", "dep", "word2"]]
}}
"""
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_mime_type='application/json',
                        temperature=0.1
                    )
                )
                
                result = json.loads(response.text)
                
                deps = []
                for d in result.get("dependencies", []):
                    if isinstance(d, list) and len(d) == 3:
                        deps.append((str(d[0]), str(d[1]), str(d[2])))
                
                return DecompositionResult(
                    sub_claims=result.get("sub_claims", [claim]),
                    logical_joiners=result.get("logical_joiners", []),
                    interpretive_fragments=result.get("interpretive_fragments", []),
                    hidden_premises=result.get("hidden_premises", []),
                    temporal_claims=result.get("temporal_claims", []),
                    causal_claims=result.get("causal_claims", []),
                    conditional_claims=result.get("conditional_claims", []),
                    statistical_claims=result.get("statistical_claims", []),
                    dependencies=deps
                )
        except Exception as e:
            logger.warning(f"LLM decomposition failed: {e}. Falling back to regex.")

    return _decompose_claim_regex(claim)

