import os
import json
import logging
from dataclasses import dataclass
from typing import List
import asyncio

from truth_mirror.source_analyzer import SourceAnalysis
from truth_mirror.perspective_synthesizer import PerspectiveGroup
try:
    from google.genai import types
except ImportError:
    types = None

logger = logging.getLogger(__name__)

@dataclass
class HiddenStory:
    title: str
    explanation: str
    supporting_facts: list[str]
    which_sources_hint_at_this: list[str]
    which_sources_suppress_this: list[str]
    significance: str

class HiddenStoryExtractor:
    async def extract(
        self,
        source_analyses: List[SourceAnalysis],
        perspective_groups: List[PerspectiveGroup],
        claim: str,
        gemini_client
    ) -> List[HiddenStory]:
        if not source_analyses:
            return []
            
        # We need to compute consensus and disputed points for the prompt
        # We will import the helper here to avoid circular imports if any
        from truth_mirror.geo_orchestrator import compute_consensus_disputes
        consensus_points, disputed_points = compute_consensus_disputes(source_analyses)
        
        consensus_str = "\n".join([f"- {p}" for p in consensus_points]) if consensus_points else "None"
        disputed_str = "\n".join([f"- {p}" for p in disputed_points]) if disputed_points else "None"
        
        omissions_parts = []
        for g in perspective_groups:
            omissions_parts.append(f"Bloc: {g.group_label} -> Omits: {g.what_they_omit}")
        formatted_omissions_per_bloc = "\n".join(omissions_parts)
        
        sources_parts = []
        for s in source_analyses:
            sources_parts.append(f"[{s.source_name}] Stance: {s.stance} | Key Claims: {', '.join(s.key_claims)}")
        formatted_all_sources = "\n".join(sources_parts)
        
        prompt = f"""You are an experienced investigative journalist and geopolitical analyst with deep knowledge of how media narratives are constructed, what states and media organisations have incentives to hide, and what patterns of omission reveal about real events.

You have been given a full analysis of {len(source_analyses)} news sources across {len(perspective_groups)} media blocs regarding the following claim:

CLAIM: {claim}

CONSENSUS FACTS (what most or all sources agree on):
{consensus_str}

DISPUTED FACTS (where sources disagree):
{disputed_str}

COLLECTIVE OMISSIONS (what each bloc is NOT saying):
{formatted_omissions_per_bloc}

ALL SOURCE SUMMARIES:
{formatted_all_sources}

Your task is to identify 2-5 hidden stories, patterns, or angles that:
- Are NOT the main narrative any source is pushing
- Emerge from CONNECTING facts that individual sources report separately
- Explain WHY certain facts are being emphasized or suppressed
- Represent what an experienced intelligence analyst or senior journalist would conclude by reading between the lines
- May involve: economic incentives, military strategy, domestic political pressures, diplomatic back-channels, historical patterns being repeated, or facts that contradict the official narrative of multiple parties simultaneously

For each hidden story, respond in this JSON format:
{{
  "title": "Short headline",
  "explanation": "3-5 sentence explanation of the hidden story or pattern.",
  "supporting_facts": ["Specific fact from sources that supports this", "..."],
  "which_sources_hint_at_this": ["source name", "..."],
  "which_sources_suppress_this": ["source name", "..."],
  "significance": "Why this matters and what it changes about understanding the claim."
}}

Return a JSON array. Be intellectually rigorous. Do not speculate wildly — ground every hidden story in specific observable facts from the sources. But do not be timid: if the facts point somewhere the mainstream narrative ignores, say so clearly.
"""
        def run_sync():
            data = None
            if gemini_client and types:
                for attempt in range(2):
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
                        logger.warning(f"Gemini hidden story extraction failed on attempt {attempt+1}: {e}")
                        import time
                        time.sleep(2)
            
            if data is None:
                import os, json, urllib.request, re
                api_key = os.environ.get("OPENROUTER_API_KEY")
                if api_key and api_key != "your_openrouter_api_key_here":
                    req_data = json.dumps({
                        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
                        "messages": [{"role": "user", "content": prompt + "\n\nRespond ONLY with the exact JSON array. No other text."}]
                    }).encode('utf-8')
                    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=req_data, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
                    with urllib.request.urlopen(req) as response:
                        resp_data = json.loads(response.read().decode('utf-8'))
                        raw_json = resp_data["choices"][0]["message"]["content"]
                        match = re.search(r'\[.*\]', raw_json, re.DOTALL)
                        if match:
                            raw_json = match.group(0)
                        data = json.loads(raw_json)
            return data

        try:
            data = await asyncio.to_thread(run_sync)
            result = []
            if data:
                for item in data:
                    result.append(HiddenStory(
                        title=item.get("title", ""),
                        explanation=item.get("explanation", ""),
                        supporting_facts=item.get("supporting_facts", []),
                        which_sources_hint_at_this=item.get("which_sources_hint_at_this", []),
                        which_sources_suppress_this=item.get("which_sources_suppress_this", []),
                        significance=item.get("significance", "")
                    ))
            return result
        except Exception as e:
            logger.error(f"Hidden story extraction failed entirely: {e}")
            return []
