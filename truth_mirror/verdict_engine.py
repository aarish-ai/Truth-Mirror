import os
import json
import logging
from dataclasses import dataclass
from typing import List
import asyncio

from truth_mirror.source_analyzer import SourceAnalysis
from truth_mirror.perspective_synthesizer import PerspectiveGroup
from truth_mirror.hidden_story_extractor import HiddenStory
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
- Return ONLY the JSON object, no other text.
"""
        def run_sync():
            data = None
            if gemini_client and types:
                import time
                for attempt in range(4):
                    try:
                        response = gemini_client.models.generate_content(
                            model="gemini-2.5-flash",
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
                        break
                    except Exception as e:
                        logger.warning(f"Gemini verdict engine failed on attempt {attempt+1}: {e}")
                        time.sleep(2 ** attempt)
            
            if data is None:
                import os, urllib.request, re, time, random
                api_key = os.environ.get("OPENROUTER_API_KEY")
                if api_key and api_key != "your_openrouter_api_key_here":
                    req_data = json.dumps({
                        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
                        "messages": [{"role": "user", "content": prompt + "\n\nRespond ONLY with the exact JSON object. No other text."}]
                    }).encode('utf-8')
                    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=req_data, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
                    
                    for attempt in range(4):
                        try:
                            with urllib.request.urlopen(req) as response:
                                resp_data = json.loads(response.read().decode('utf-8'))
                                raw_json = resp_data["choices"][0]["message"]["content"]
                                match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                                if match:
                                    raw_json = match.group(0)
                                data = json.loads(raw_json)
                                break
                        except Exception as e:
                            wait_time = (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"OpenRouter verdict generation failed on attempt {attempt+1}. Waiting {wait_time:.2f}s before retry. Error: {e}")
                            time.sleep(wait_time)
                            
            if data is None:
                logger.warning("Falling back to local Ollama for verdict generation.")
                ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/generate"
                payload = {
                    "model": "qwen2.5:3b",
                    "prompt": prompt + "\n\nRespond ONLY with the exact JSON object. No other text.",
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1}
                }
                ollama_req = urllib.request.Request(ollama_url, data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(ollama_req, timeout=120) as response:
                        resp_data = json.loads(response.read().decode('utf-8'))
                        raw_json = resp_data.get("response", "").strip()
                        raw_json = raw_json.removeprefix("```json").removesuffix("```").strip()
                        raw_json = raw_json.removeprefix("```").removesuffix("```").strip()
                        try:
                            data = json.loads(raw_json)
                        except Exception:
                            start = raw_json.find('{')
                            end = raw_json.rfind('}')
                            if start != -1 and end != -1:
                                data = json.loads(raw_json[start:end+1])
                            else:
                                raise ValueError("Could not extract JSON object from Ollama response")
                                
                        if isinstance(data, list):
                            data = data[0] if len(data) > 0 else {}
                        if not isinstance(data, dict):
                            data = {}
                except Exception as e:
                    logger.error(f"Local Ollama fallback failed: {e}")
            return data

        try:
            data = await asyncio.to_thread(run_sync)
            if data:
                return IntelligenceVerdict(
                    verdict=data.get("verdict", "UNVERIFIABLE"),
                    confidence=float(data.get("confidence", 0.0)),
                    confidence_label=data.get("confidence_label", "LOW"),
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
