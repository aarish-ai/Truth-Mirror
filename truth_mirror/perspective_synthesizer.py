import os
import json
import logging
from dataclasses import dataclass
from typing import List
import asyncio

from truth_mirror.source_analyzer import SourceAnalysis
from truth_mirror.source_registry import ALIGNMENT_GROUP_LABELS
from truth_mirror.run_tracker import tracker
from truth_mirror.llm_fallback import LLMFallbackChain
from truth_mirror.groq_router import GROQ_ANALYSIS_PRIMARY

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
    async def synthesize(self, source_analyses: List[SourceAnalysis], claim: str, gemini_client, temporal_context=None) -> List[PerspectiveGroup]:
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
        
        claim_with_context = claim
        if temporal_context and hasattr(temporal_context, 'date_qualifier') and temporal_context.date_qualifier:
            claim_with_context = f"{claim} (Timeframe: {temporal_context.date_qualifier})"
            
        prompt = f"""You are a senior geopolitical intelligence analyst. Below is a collection of news source analyses grouped by media alignment. Your job is to characterize what each media bloc is collectively saying about the given claim.

CLAIM: {claim_with_context}

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
            chain = LLMFallbackChain(
                sequence=["gemini", "groq", "openrouter"],
                models={
                    "gemini": "gemini-3.5-flash",
                    "groq": GROQ_ANALYSIS_PRIMARY,
                    "openrouter": "qwen/qwen3-next-80b-a3b-instruct:free"
                },
                tracker_module="perspective_synthesis",
                temperature=0.2,
                max_tokens=4096
            )
            data = chain.execute(prompt)
            if data is None:
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

