import os
import json
import logging
from dataclasses import dataclass
from typing import List
import asyncio

from truth_mirror.source_analyzer import SourceAnalysis
from truth_mirror.source_registry import ALIGNMENT_GROUP_LABELS
from truth_mirror.run_tracker import tracker
try:
    from google.genai import types
except ImportError:
    types = None

try:
    from json_repair import repair_json
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class PerspectiveGroup:
    group_label: str
    alignment: str
    source_count: int
    source_names: list[str]
    
    collective_stance: str
    collective_narrative: str
    what_they_emphasize: str
    what_they_omit: str
    internal_disagreements: str
    credibility_note: str

class PerspectiveSynthesizer:
    async def synthesize(self, source_analyses: List[SourceAnalysis], claim: str, gemini_client) -> List[PerspectiveGroup]:
        if not source_analyses:
            return []
            
        groups_dict = {}
        for sa in source_analyses:
            groups_dict.setdefault(sa.alignment, []).append(sa)
            
        formatted_groups_parts = []
        for alignment, sources in groups_dict.items():
            label = ALIGNMENT_GROUP_LABELS.get(alignment, alignment.title())
            parts = [f"--- [{label}] ({len(sources)} sources) ---"]
            for s in sources:
                parts.append(f"Source: {s.source_name} | Stance: {s.stance} | Summary: {s.summary} | Emphasized: {s.what_emphasized} | Omitted: {s.what_omitted}")
            formatted_groups_parts.append("\n".join(parts))
            
        formatted_groups = "\n\n".join(formatted_groups_parts)
        
        prompt = f"""You are a senior geopolitical intelligence analyst. Below is a collection of news source analyses grouped by media alignment. Your job is to characterize what each media bloc is collectively saying about the given claim.

CLAIM: {claim}

SOURCE ANALYSES BY BLOC:
{formatted_groups}

For EACH bloc present, produce a JSON object in this format:
{{
  "group_label": "...",
  "alignment": "...",
  "collective_stance": "SUPPORTS | CONTRADICTS | PARTIALLY_SUPPORTS | INCONCLUSIVE | SPLIT",
  "collective_narrative": "2-3 sentences describing the bloc's overall message.",
  "what_they_emphasize": "The dominant talking points or frames used across this group.",
  "what_they_omit": "Relevant facts that appear absent from ALL sources in this group.",
  "internal_disagreements": "Any notable divergence within the group, or empty string.",
  "credibility_note": "Why this group's coverage should be trusted or treated cautiously on this topic."
}}

Return ONLY a valid JSON array. The array must contain ONLY JSON objects. Do NOT include any strings, explanations, or preamble text as array elements. Do NOT wrap the array in an object. The first character of your response must be '[' and the last must be ']'. Any non-object element will cause a system failure.
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
                                    temperature=0.1,
                                    max_output_tokens=4096
                                )
                            )
                            raw_json = response.text
                            if raw_json.startswith("```json"):
                                raw_json = raw_json.strip("` \n").removeprefix("json")
                            try:
                                data = json.loads(raw_json)
                            except json.JSONDecodeError:
                                if JSON_REPAIR_AVAILABLE:
                                    repaired = repair_json(raw_json, return_objects=True)
                                    if isinstance(repaired, list) and repaired:
                                        data = repaired
                                        logger.info("[PerspectiveSynthesizer] JSON repaired successfully.")
                                    else:
                                        logger.warning("[PerspectiveSynthesizer] JSON repair did not produce a valid list.")
                                        data = None
                                else:
                                    logger.warning("[PerspectiveSynthesizer] JSON parse failed and json_repair not available.")
                                    data = None
                            
                            if data is not None:
                                tracker.record("perspective_synthesis", "gemini-3.5-flash", "gemini", "success")
                            break
                        except Exception as e:
                            logger.warning(f"Gemini perspective synthesis failed on attempt {attempt+1}: {e}")
                            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                                logger.warning("Rotating Gemini key due to 429 in perspective_synthesizer...")
                                tracker.record("perspective_synthesis", "gemini-3.5-flash", "gemini", "rate_limited")
                                rotate_gemini_key()
                except Exception:
                    pass
            
            if data is None:
                # TRY GROQ BEFORE OPENROUTER
                try:
                    from truth_mirror.groq_router import GROQ_ANALYSIS_PRIMARY, call_groq_with_key_rotation
                    groq_prompt = (
                        prompt +
                        '\n\nIMPORTANT: Respond with a JSON OBJECT containing a single '
                        'key "perspectives" whose value is the array of bloc objects. '
                        'Example: {"perspectives": [{...}, {...}]}'
                    )
                    groq_payload = {
                        "model": GROQ_ANALYSIS_PRIMARY,
                        "messages": [{"role": "user", "content": groq_prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "max_tokens": 4096
                    }
                    groq_content, groq_status = call_groq_with_key_rotation(
                        payload=groq_payload,
                        timeout=60,
                        log_prefix="[PerspectiveSynthesizer]"
                    )
                    if groq_status == "success" and groq_content:
                        try:
                            parsed = json.loads(groq_content)
                            if isinstance(parsed, list):
                                data = parsed
                            elif isinstance(parsed, dict):
                                for v in parsed.values():
                                    if isinstance(v, list) and v:
                                        data = v
                                        break
                            logger.info("[PerspectiveSynthesizer] Groq fallback succeeded.")
                        except json.JSONDecodeError:
                            if JSON_REPAIR_AVAILABLE:
                                repaired = repair_json(groq_content, return_objects=True)
                                if isinstance(repaired, list):
                                    data = repaired
                                elif isinstance(repaired, dict):
                                    for v in repaired.values():
                                        if isinstance(v, list) and v:
                                            data = v
                                            break
                                if data:
                                    logger.info("[PerspectiveSynthesizer] JSON repaired successfully.")
                                else:
                                    logger.warning("[PerspectiveSynthesizer] JSON repair did not produce a valid list.")
                                    data = None
                            else:
                                logger.warning("[PerspectiveSynthesizer] JSON parse failed and json_repair not available.")
                                data = None
                        if data is not None:
                            tracker.record("perspective_synthesis", GROQ_ANALYSIS_PRIMARY, "groq", "fallback_used")
                    else:
                        data = None
                except Exception as e:
                    logger.warning(f"[PerspectiveSynthesizer] Groq fallback failed: {e}")
                    data = None

            if data is None:
                import os, urllib.request, re, time, random
                api_key = os.environ.get("OPENROUTER_API_KEY")
                if api_key and api_key != "your_openrouter_api_key_here":
                    req_data = json.dumps({
                        "model": "qwen/qwen3-next-80b-a3b-instruct:free",
                        "messages": [{"role": "user", "content": prompt + "\n\nRespond ONLY with the exact JSON array. No other text."}]
                    }).encode('utf-8')
                    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=req_data, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
                    
                    for attempt in range(4):
                        try:
                            with urllib.request.urlopen(req, timeout=30) as response:
                                resp_data = json.loads(response.read().decode('utf-8'))
                                raw_json = resp_data["choices"][0]["message"]["content"]
                                match = re.search(r'\[.*\]', raw_json, re.DOTALL)
                                if match:
                                    raw_json = match.group(0)
                                try:
                                    data = json.loads(raw_json)
                                except json.JSONDecodeError:
                                    if JSON_REPAIR_AVAILABLE:
                                        repaired = repair_json(raw_json, return_objects=True)
                                        if isinstance(repaired, list) and repaired:
                                            data = repaired
                                            logger.info("[PerspectiveSynthesizer] JSON repaired successfully.")
                                        else:
                                            logger.warning("[PerspectiveSynthesizer] JSON repair did not produce a valid list.")
                                            data = None
                                    else:
                                        logger.warning("[PerspectiveSynthesizer] JSON parse failed and json_repair not available.")
                                        data = None
                                if data is not None:
                                    tracker.record("perspective_synthesis", "qwen/qwen3-next-80b-a3b-instruct:free", "openrouter", "fallback_used")
                                break
                        except Exception as e:
                            wait_time = (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"OpenRouter perspective synthesis failed on attempt {attempt+1}. Waiting {wait_time:.2f}s before retry. Error: {e}")
                            time.sleep(wait_time)
                            
            if data is None:
                tracker.record("perspective_synthesis", "ALL_FAILED", "none", "failed")
                logger.error("All API fallbacks failed for perspective synthesis.")
            return data

        try:
            data = await asyncio.to_thread(run_sync)
            result = []
            if data:
                for item in data:
                    if not isinstance(item, dict):
                        logger.warning(f"[PerspectiveSynthesizer] Skipping non-dict item in response: {type(item)}")
                        continue
                    alignment = item.get("alignment", "unknown")
                    sources_in_group = groups_dict.get(alignment, [])
                    source_names = list(set([s.source_name for s in sources_in_group]))
                    
                    result.append(PerspectiveGroup(
                        group_label=item.get("group_label", ALIGNMENT_GROUP_LABELS.get(alignment, alignment)),
                        alignment=alignment,
                        source_count=len(sources_in_group),
                        source_names=source_names,
                        collective_stance=item.get("collective_stance", "INCONCLUSIVE"),
                        collective_narrative=item.get("collective_narrative", ""),
                        what_they_emphasize=item.get("what_they_emphasize", ""),
                        what_they_omit=item.get("what_they_omit", ""),
                        internal_disagreements=item.get("internal_disagreements", ""),
                        credibility_note=item.get("credibility_note", "")
                    ))
            return result
        except Exception as e:
            logger.error(f"Perspective synthesis failed entirely: {e}")
            return []

