import os
import re
import json
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Fallback regex if Ollama fails or returns invalid JSON
GEO_KEYWORDS = re.compile(
    r"\b(war|military|sanctions|treaty|diplomat|diplomacy|president|prime minister|"
    r"invasion|missile|border|election|geopolitical|international|united nations|nato|eu|foreign|policy)\b",
    re.IGNORECASE
)

class GeoClassifier:
    """
    Classifies whether a claim is geopolitical in nature.
    Uses a local Ollama model (default: qwen2.5:3b) with a strict JSON format constraint.
    Falls back to regex keywords if the LLM is unavailable or fails.
    """
    
    def __init__(self, ollama_url: str = None, model: str = "qwen2.5:3b"):
        base_url = (ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip('/')
        if not base_url.endswith("/api"):
            base_url += "/api"
        self.ollama_url = base_url
        self.model = model

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
        
        url = f"{self.ollama_url}/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            
            result_text = response.json().get("response", "").strip()
            result = json.loads(result_text)
            
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
            
        except Exception as e:
            logger.warning(f"Ollama geo-classification failed ({e}). Using regex fallback.")
            return self._regex_fallback(claim)

    def _regex_fallback(self, claim: str) -> Dict[str, Any]:
        """
        Fallback classification using keyword matching if Ollama fails.
        """
        is_geo = bool(GEO_KEYWORDS.search(claim))
        reason = "Regex fallback matched geopolitical keywords." if is_geo else "Regex fallback found no geopolitical keywords."
        
        return {
            "is_geopolitical": is_geo,
            "reason": reason,
            "involved_parties": ["unknown"],
            "claim_subtype": "unknown"
        }
