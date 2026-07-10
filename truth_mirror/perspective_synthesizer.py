import os
import json
import logging
from dataclasses import dataclass
from typing import List
import asyncio

from truth_mirror.source_analyzer import SourceAnalysis
from truth_mirror.source_registry import ALIGNMENT_GROUP_LABELS
try:
    from google.genai import types
except ImportError:
    types = None

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

Return a JSON array of these objects. No other text.
"""
        def run_sync():
            data = None
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    import time
                    if attempt > 0:
                        time.sleep(2)
                        
                    from truth_mirror.key_rotator import get_current_key, rotate_gemini_key
                    api_key = get_current_key()
                    if api_key and types:
                        gemini_client = genai.Client(api_key=api_key)
                        
                    if gemini_client and types:
                        try:
                            response = gemini_client.models.generate_content(
                                model="gemini-3.5-flash",
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    temperature=0.1,
                                )
                            )
                            raw_json = response.text
                            if raw_json.startswith("```json"):
                                raw_json = raw_json.strip("` \n").removeprefix("json")
                            data = json.loads(raw_json)
                            break
                        except Exception as e:
                            logger.warning(f"Gemini perspective synthesis failed on attempt {attempt+1}: {e}")
                            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                                logger.warning("Rotating Gemini key due to 429 in perspective_synthesizer...")
                                rotate_gemini_key()
                except Exception:
                    pass
            
            if data is None:
                import os, urllib.request, re, time, random
                api_key = os.environ.get("OPENROUTER_API_KEY")
                if api_key and api_key != "your_openrouter_api_key_here":
                    req_data = json.dumps({
                        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
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
                                data = json.loads(raw_json)
                                break
                        except Exception as e:
                            wait_time = (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"OpenRouter perspective synthesis failed on attempt {attempt+1}. Waiting {wait_time:.2f}s before retry. Error: {e}")
                            time.sleep(wait_time)
                            
            if data is None:
                logger.error("All API fallbacks failed for perspective synthesis.")
            return data

        try:
            data = await asyncio.to_thread(run_sync)
            result = []
            if data:
                for item in data:
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
