import os
import re
import json
import logging
import requests
from typing import Dict, Any
from dotenv import load_dotenv
from truth_mirror.llm_fallback import LLMFallbackChain
from truth_mirror.groq_router import GROQ_SIMPLE_MODEL
load_dotenv()

logger = logging.getLogger(__name__)

# Fallback regex if LLM fails or returns invalid JSON
GEO_KEYWORDS = re.compile(
    r"\b(war|military|sanctions|treaty|diplomat|diplomacy|president|prime minister|"
    r"invasion|missile|border|election|geopolitical|international|united nations|nato|eu|foreign|policy)\b",
    re.IGNORECASE
)

class GeoClassifier:
    """
    Classifies whether a claim is geopolitical in nature.
    Uses Groq (GROQ_SIMPLE_MODEL) with a strict JSON format constraint.
    Falls back to OpenRouter then regex keywords if the LLMs are unavailable or fail.
    """
    
    def __init__(self):
        pass

    def classify(self, claim: str) -> Dict[str, Any]:
        """
        Determines if a claim is geopolitical.
        Returns a dictionary containing:
        - is_geopolitical (bool)
        - reason (str)
        - involved_parties (list of str)
        - claim_subtype (str)
        """
        prompt = f"""You are an expert geopolitical intelligence analyst.
Analyze the following claim and determine if it is geopolitical in nature.
A claim is geopolitical if it involves international relations, government policies, state actors, military actions, elections, or significant global economic events.

Claim: "{claim}"

Respond strictly with a JSON object having the following keys:
- "is_geopolitical": boolean indicating if the claim is geopolitical.
- "reason": brief string explaining why it is or isn't geopolitical.
- "involved_parties": list of strings naming the countries, leaders, or organizations involved (empty list if none).
- "claim_subtype": string indicating the subtype (e.g., "military", "diplomatic", "economic", "domestic_politics", "non_political").

Do not include any other text, markdown formatting, or explanations. Only output the raw JSON object.
"""
        
        chain = LLMFallbackChain(
            sequence=["groq", "openrouter"],
            models={
                "groq": GROQ_SIMPLE_MODEL,
                "openrouter": "qwen/qwen3-next-80b-a3b-instruct:free"
            },
            tracker_module="geo_classifier",
            temperature=0.1,
            max_tokens=512
        )
        
        result = chain.execute(prompt)
        
        if result:
            is_geo = bool(result.get("is_geopolitical", False))
            reason = str(result.get("reason", "No reason provided"))
            parties = result.get("involved_parties", [])
            if not isinstance(parties, list):
                parties = [str(parties)]
            subtype = str(result.get("claim_subtype", "unknown"))
            
            return {
                "is_geopolitical": is_geo,
                "reason": reason,
                "involved_parties": parties,
                "claim_subtype": subtype
            }
        else:
            logger.warning("All geo-classification fallbacks failed. Using regex fallback.")
            return self._regex_fallback(claim)

    def _regex_fallback(self, claim: str) -> Dict[str, Any]:
        """
        Fallback classification using keyword matching if LLMs fail.
        """
        is_geo = bool(GEO_KEYWORDS.search(claim))
        reason = "Regex fallback matched geopolitical keywords." if is_geo else "Regex fallback found no geopolitical keywords."
        
        return {
            "is_geopolitical": is_geo,
            "reason": reason,
            "involved_parties": ["unknown"],
            "claim_subtype": "unknown"
        }
