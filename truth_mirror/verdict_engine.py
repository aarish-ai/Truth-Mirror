import os
import json
import logging
from dataclasses import dataclass
from typing import List
import asyncio

from truth_mirror.source_analyzer import SourceAnalysis
from truth_mirror.perspective_synthesizer import PerspectiveGroup
from truth_mirror.hidden_story_extractor import HiddenStory
from truth_mirror.run_tracker import tracker
try:
    from google.genai import types
except ImportError:
    types = None

logger = logging.getLogger(__name__)

@dataclass
class IntelligenceVerdict:
    verdict: str
    confidence: float
    confidence_label: str
    
    one_line_verdict: str
    full_reasoning: str
    
    what_is_true: str
    what_is_false: str
    what_is_unclear: str
    
    strongest_evidence_for: str
    strongest_evidence_against: str
    
    source_quality_note: str

class VerdictEngine:
    async def generate(
        self,
        source_analyses: List[SourceAnalysis],
        perspective_groups: List[PerspectiveGroup],
        hidden_stories: List[HiddenStory],
        claim: str,
        gemini_client
    ) -> IntelligenceVerdict:
    
        support_count = sum(1 for s in source_analyses if s.stance == "SUPPORTS")
        contradict_count = sum(1 for s in source_analyses if s.stance == "CONTRADICTS")
        partial_count = sum(1 for s in source_analyses if s.stance == "PARTIALLY_SUPPORTS")
        inconclusive_count = sum(1 for s in source_analyses if s.stance in ["INCONCLUSIVE", "BACKGROUND_ONLY"])
        
        stance_parts = []
        for s in source_analyses:
            stance_parts.append(f"[{s.source_name}] ({s.alignment}) -> {s.stance} ({s.stance_confidence}): {s.stance_reasoning}")
        formatted_source_stances = "\n".join(stance_parts)
        
        narrative_parts = []
        for g in perspective_groups:
            narrative_parts.append(f"[{g.group_label}] Stance: {g.collective_stance}\nNarrative: {g.collective_narrative}")
        formatted_bloc_narratives = "\n".join(narrative_parts)
        
        hidden_story_titles = "\n".join([f"- {h.title}" for h in hidden_stories])
        
        prompt = f"""You are a senior fact-checker and intelligence analyst issuing a final verdict on a claim.

CLAIM: {claim}

EVIDENCE SUMMARY:
Total sources analyzed: {len(source_analyses)}
Supporting: {support_count} | Contradicting: {contradict_count} | Partially supporting: {partial_count} | Inconclusive: {inconclusive_count}

SOURCE STANCE BREAKDOWN:
{formatted_source_stances}

BLOC NARRATIVES:
{formatted_bloc_narratives}

HIDDEN STORY TITLES & OMISSIONS:
{hidden_story_titles}

Based on all of the above, issue a final verdict in this JSON format:
{{
  "verdict": "SUPPORTED | PARTIALLY_SUPPORTED | CONTRADICTED | MISLEADING | UNVERIFIABLE | MEDIA BLACKOUT",
  "confidence": 0.0,
  "confidence_label": "HIGH | MODERATE | LOW",
  "one_line_verdict": "Single sentence plain English verdict.",
  "full_reasoning": "3-5 sentences explaining the verdict and what evidence drove it. EXPLICITLY incorporate any profound Hidden Stories or narrative omissions into your reasoning.",
  "what_is_true": "The verified parts of the claim.",
  "what_is_false": "The disproven parts of the claim.",
  "what_is_unclear": "What remains unconfirmed.",
  "strongest_evidence_for": "Best specific evidence supporting the claim.",
  "strongest_evidence_against": "Best specific evidence contradicting it.",
  "source_quality_note": "Assessment of source balance and potential gaps in the evidence package."
}}

Verdict definitions:
- SUPPORTED: Strong corroborated evidence confirms the claim across independent sources
- PARTIALLY_SUPPORTED: Core claim has some truth but key details are wrong, exaggerated, or missing
- CONTRADICTED: Multiple credible independent sources directly disprove the claim
- MISLEADING: Claim uses true facts in a way that creates a false overall impression
- UNVERIFIABLE: Insufficient credible independent evidence to confirm or deny
- MEDIA BLACKOUT: Widespread, coordinated silence or refusal to engage with the claim in a way that signals narrative control or suppression (e.g., all sources are 'INCONCLUSIVE' rather than 'CONTRADICTING').
- Weight independent sources (wire services, OSINT, independent journalism) more heavily than state media
- State media on both sides corroborating = weaker signal than independent sources corroborating
- Return ONLY a valid JSON object. Do NOT include any strings, explanations, or preamble text. The first character of your response must be '{' and the last must be '}'. Any non-object element will cause a system failure.
"""
        def run_sync():
            import os, time, urllib.request, re, random
            data = None
            gemini_client = None
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    import time
                    if attempt > 0:
                        time.sleep(2)
                        
                    from truth_mirror.key_rotator import get_current_key, rotate_gemini_key
                    api_key = get_current_key()
                    if api_key and types:
                        from google import genai
                        gemini_client = genai.Client(api_key=api_key)
                        
                    if gemini_client and types:
                        try:
                            response = gemini_client.models.generate_content(
                                model="gemini-3.5-flash",
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
                            if data is not None:
                                tracker.record("verdict_generation", "gemini-3.5-flash", "gemini", "success")
                            break
                        except Exception as e:
                            logger.warning(f"Gemini verdict engine failed on attempt {attempt+1}: {e}")
                            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                                logger.warning("Rotating Gemini key due to 429 in verdict_engine...")
                                tracker.record("verdict_generation", "gemini-3.5-flash", "gemini", "rate_limited")
                                rotate_gemini_key()
                except Exception:
                    pass
            
            if data is None:
                # TRY GROQ BEFORE OPENROUTER
                try:
                    from truth_mirror.groq_router import GROQ_ANALYSIS_PRIMARY, call_groq_with_key_rotation
                    groq_payload = {
                        "model": GROQ_ANALYSIS_PRIMARY,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "max_tokens": 4096
                    }
                    groq_content, groq_status = call_groq_with_key_rotation(
                        payload=groq_payload,
                        timeout=60,
                        log_prefix="[VerdictEngine]"
                    )
                    if groq_status == "success" and groq_content:
                        try:
                            data = json.loads(groq_content)
                            logger.info("[VerdictEngine] Groq fallback succeeded.")
                        except json.JSONDecodeError:
                            logger.warning("[VerdictEngine] JSON parse failed.")
                            data = None
                        if data is not None:
                            tracker.record("verdict_generation", GROQ_ANALYSIS_PRIMARY, "groq", "fallback_used")
                    else:
                        data = None
                except Exception as e:
                    logger.warning(f"[VerdictEngine] Groq fallback failed: {e}")
                    data = None

            if data is None:
                import os, urllib.request, re, time, random
                api_key = os.environ.get("OPENROUTER_API_KEY")
                if api_key and api_key != "your_openrouter_api_key_here":
                    req_data = json.dumps({
                        "model": "qwen/qwen3-next-80b-a3b-instruct:free",
                        "messages": [{"role": "user", "content": prompt + "\n\nRespond ONLY with the exact JSON object. No other text."}]
                    }).encode('utf-8')
                    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=req_data, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
                    
                    for attempt in range(4):
                        try:
                            with urllib.request.urlopen(req, timeout=30) as response:
                                resp_data = json.loads(response.read().decode('utf-8'))
                                raw_json = resp_data["choices"][0]["message"]["content"]
                                match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                                if match:
                                    raw_json = match.group(0)
                                data = json.loads(raw_json)
                                if data is not None:
                                    tracker.record("verdict_generation", "qwen/qwen3-next-80b-a3b-instruct:free", "openrouter", "fallback_used")
                                break
                        except Exception as e:
                            wait_time = (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"OpenRouter verdict generation failed on attempt {attempt+1}. Waiting {wait_time:.2f}s before retry. Error: {e}")
                            time.sleep(wait_time)
                            
            if data is None:
                tracker.record("verdict_generation", "ALL_FAILED", "none", "failed")
                logger.error("All API fallbacks failed for verdict generation.")
            return data

        try:
            data = await asyncio.to_thread(run_sync)
            if data and not isinstance(data, dict):
                logger.warning(f"Verdict data is not a dict: {type(data)}")
                data = None
            if data:
                raw_confidence = float(data.get("confidence", 0.0))
                if raw_confidence > 0.85:
                    confidence_label = "Very High"
                elif raw_confidence > 0.50:
                    confidence_label = "High"
                elif raw_confidence > 0.30:
                    confidence_label = "Moderate"
                else:
                    confidence_label = "Low"
                    
                return IntelligenceVerdict(
                    verdict=data.get("verdict", "UNVERIFIABLE"),
                    confidence=raw_confidence,
                    confidence_label=confidence_label,
                    one_line_verdict=data.get("one_line_verdict", ""),
                    full_reasoning=data.get("full_reasoning", ""),
                    what_is_true=data.get("what_is_true", ""),
                    what_is_false=data.get("what_is_false", ""),
                    what_is_unclear=data.get("what_is_unclear", ""),
                    strongest_evidence_for=data.get("strongest_evidence_for", ""),
                    strongest_evidence_against=data.get("strongest_evidence_against", ""),
                    source_quality_note=data.get("source_quality_note", "")
                )
        except Exception as e:
            logger.error(f"Verdict engine failed entirely: {e}")
            
        return IntelligenceVerdict(
            verdict="UNVERIFIABLE",
            confidence=0.0,
            confidence_label="LOW",
            one_line_verdict="Verdict generation failed due to an error.",
            full_reasoning="System was unable to synthesize the verdict.",
            what_is_true="",
            what_is_false="",
            what_is_unclear="",
            strongest_evidence_for="",
            strongest_evidence_against="",
            source_quality_note=""
        )

