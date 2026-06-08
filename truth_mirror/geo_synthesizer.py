import os
import json
import logging
from typing import Any
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

from truth_mirror.models import (
    GeopoliticalResult,
    GeoStory,
    GeoActor,
    GeoDisputeAnalysis,
    GeoNarrative,
)

logger = logging.getLogger(__name__)

GEO_SYNTHESIS_PROMPT = """
You are a senior geopolitical intelligence analyst and investigative journalist.
You have access to evidence from multiple sources with different geopolitical alignments.

Your task is to analyze the following claim and produce a structured intelligence report.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORIGINAL CLAIM: "{claim}"
CLAIM TYPE: {claim_subtype}
PARTIES INVOLVED: {involved_parties}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EVIDENCE BY PERSPECTIVE:
{evidence_by_perspective}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INSTRUCTIONS:

STEP 1 — VERDICT
Determine the verdict for the original claim based on the evidence.
Use ONLY these verdicts:
- "Supported": Multiple credible, independent sources from DIFFERENT geopolitical
  alignments confirm the claim. Minimal dispute on core facts.
- "Partially Supported": Core facts are confirmed by credible sources, but details
  are disputed, or only one geopolitical bloc confirms it.
- "Unclear": Sources fundamentally disagree on whether the core event even occurred.
  Neither side has overwhelming evidence. Significant dispute exists.
- "Partially Unsupported": The claim's core facts are doubted by most credible sources
  but some state media or low-credibility sources support it.
- "False": Multiple credible, independent sources across geopolitical alignments
  directly contradict the claim. The claim is demonstrably incorrect.

STEP 2 — STORY (Contextual Narrative)
Write a journalist-quality contextual background (200-400 words).
This section explains:
a) What is the background context of this claim? What tensions/history led here?
b) What exactly happened (or is alleged to have happened) according to available evidence?
c) What is the current state of the situation?
d) Who are the key actors and what are their stated positions?
Be specific: cite which sources say what. Note where sources agree and where they diverge.
Write in third-person journalistic style. Do NOT take sides.

STEP 3 — DISPUTE ANALYSIS (only if sources meaningfully disagree)
If significant narrative divergence exists between source groups, analyze:
a) WHAT do sources agree on? (the undisputed facts)
b) WHERE does the divergence begin? (the contested claims)
c) WESTERN/ALLIED SOURCES claim: [summarize their narrative]
   Evidence they cite: [list evidence points]
d) NON-WESTERN/OPPOSING SOURCES claim: [summarize their narrative]
   Evidence they cite: [list evidence points]
e) CREDIBILITY ASSESSMENT: Which narrative has stronger evidentiary support?
   Consider: primary sources vs secondary, on-the-ground reporting vs official
   statements, consistency across independent sources.
f) KNOWN BIAS FACTORS: Which sources have documented bias in this type of conflict?
   Why might each bloc frame the story this way?
g) MOST LIKELY GROUND TRUTH: Based on the totality of evidence, what most probably
   happened? State your confidence (high/medium/low) and why.

Set "has_dispute" to false and omit dispute_analysis if all major source groups
agree on the core facts.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL REASONING RULES:
1. If a country officially denies an action but satellite imagery, NGO reports, or
   journalists on the ground confirm it, weight the physical evidence over the denial.
2. If only state media from one country reports an event, treat it as "unverified" not
   "confirmed." Note this explicitly.
3. Apply temporal logic: if a ceasefire was announced and there is no subsequent news
   of resumption, assume it holds until contradicted.
4. If a leader/government is in power with no news of removal, assume they are still
   in power.
5. Do not hallucinate. If a piece of information is not present in the evidence,
   say "not confirmed in available sources."

Respond ONLY with this exact JSON (no markdown, no preamble):
{{
  "verdict": "Supported|Partially Supported|Unclear|Partially Unsupported|False",
  "confidence": <float 0.0-1.0>,
  "verdict_reasoning": "<2-3 sentences explaining why this verdict was chosen>",
  "source_agreement_level": "high|moderate|low|none",
  "story": {{
    "headline": "<journalist-style one-line headline for this claim>",
    "background": "<paragraph 1: historical context and tensions leading to this>",
    "current_situation": "<paragraph 2: what happened/is happening now>",
    "key_actors": [
      {{"name": "...", "role": "...", "stated_position": "..."}}
    ],
    "timeline_hints": ["<event 1>", "<event 2>"],
    "sources_agreeing_on": "<what ALL major source groups confirm>"
  }},
  "has_dispute": true|false,
  "dispute_analysis": {{
    "undisputed_facts": ["<fact 1>", "<fact 2>"],
    "contested_claims": ["<contested point 1>", "<contested point 2>"],
    "narratives": [
      {{
        "bloc": "Western/Allied Media",
        "claim": "<their version of events>",
        "evidence_strength": "strong|moderate|weak",
        "key_evidence": ["<source 1 excerpt>", "<source 2 excerpt>"],
        "known_bias": "<documented bias tendency of this bloc in this type of conflict>"
      }},
      {{
        "bloc": "Non-Western/Opposing Media",
        "claim": "<their version of events>",
        "evidence_strength": "strong|moderate|weak",
        "key_evidence": ["<source 1 excerpt>", "<source 2 excerpt>"],
        "known_bias": "<documented bias tendency>"
      }}
    ],
    "most_likely_ground_truth": "<Gemini's reasoned assessment>",
    "ground_truth_confidence": "high|medium|low",
    "ground_truth_reasoning": "<why this assessment was reached>"
  }},
  "key_sources": [
    {{"title": "...", "publisher": "...", "perspective": "...", "url": "...", "stance": "supports|contradicts|neutral"}}
  ],
  "missing_evidence": ["<what additional evidence would resolve remaining uncertainty>"]
}}
"""

class GeoSynthesizer:
    def __init__(self, client: Any | None = None):
        self.client = client if client else (genai.Client() if GENAI_AVAILABLE else None)
        self.model_name = "gemini-2.0-flash"

    def synthesize(
        self,
        claim: str,
        claim_subtype: str,
        involved_parties: str,
        evidence_by_perspective: str,
        evidence_count: int = 0,
        sub_claims: list[str] | None = None,
    ) -> GeopoliticalResult:
        prompt = GEO_SYNTHESIS_PROMPT.format(
            claim=claim,
            claim_subtype=claim_subtype,
            involved_parties=involved_parties,
            evidence_by_perspective=evidence_by_perspective,
        )

        if not GENAI_AVAILABLE or not self.client:
            logger.warning("google-genai is not available. Returning fallback GeopoliticalResult.")
            return GeopoliticalResult(
                original_claim=claim,
                is_geopolitical=True,
                verdict="Unclear",
                confidence=0.0,
                verdict_reasoning="Synthesis disabled (google-genai not installed).",
                key_sources=[],
                sub_claims=sub_claims or [],
                evidence_count=evidence_count
            )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            
            raw_json = response.text
            if raw_json.startswith("```json"):
                raw_json = raw_json.strip("` \n").removeprefix("json")
            data = json.loads(raw_json)
        except Exception as e:
            logger.error(f"Gemini synthesis failed: {e}")
            return GeopoliticalResult(
                original_claim=claim,
                is_geopolitical=True,
                verdict="Unclear",
                confidence=0.0,
                verdict_reasoning=f"Synthesis failed due to API or parsing error: {e}",
            )

        # Parse Story
        story_obj = None
        if "story" in data and data["story"]:
            s_data = data["story"]
            actors = []
            for a in s_data.get("key_actors", []):
                actors.append(
                    GeoActor(
                        name=a.get("name", ""),
                        role=a.get("role", ""),
                        stated_position=a.get("stated_position", "")
                    )
                )
            story_obj = GeoStory(
                headline=s_data.get("headline", ""),
                background=s_data.get("background", ""),
                current_situation=s_data.get("current_situation", ""),
                key_actors=actors,
                timeline_hints=s_data.get("timeline_hints", []),
                sources_agreeing_on=s_data.get("sources_agreeing_on", "")
            )

        # Parse Dispute Analysis
        dispute_obj = None
        has_dispute = data.get("has_dispute", False)
        if has_dispute and "dispute_analysis" in data and data["dispute_analysis"]:
            d_data = data["dispute_analysis"]
            narratives = []
            for n in d_data.get("narratives", []):
                narratives.append(
                    GeoNarrative(
                        bloc=n.get("bloc", ""),
                        claim=n.get("claim", ""),
                        evidence_strength=n.get("evidence_strength", ""),
                        key_evidence=n.get("key_evidence", []),
                        known_bias=n.get("known_bias", "")
                    )
                )
            dispute_obj = GeoDisputeAnalysis(
                undisputed_facts=d_data.get("undisputed_facts", []),
                contested_claims=d_data.get("contested_claims", []),
                narratives=narratives,
                most_likely_ground_truth=d_data.get("most_likely_ground_truth", ""),
                ground_truth_confidence=d_data.get("ground_truth_confidence", ""),
                ground_truth_reasoning=d_data.get("ground_truth_reasoning", "")
            )

        return GeopoliticalResult(
            original_claim=claim,
            is_geopolitical=True,
            verdict=data.get("verdict", "Unclear"),
            confidence=float(data.get("confidence", 0.0)),
            verdict_reasoning=data.get("verdict_reasoning", ""),
            source_agreement_level=data.get("source_agreement_level", "none"),
            story=story_obj,
            has_dispute=has_dispute,
            dispute_analysis=dispute_obj,
            key_sources=data.get("key_sources", []),
            missing_evidence=data.get("missing_evidence", []),
            sub_claims=sub_claims or [],
            evidence_count=evidence_count
        )
