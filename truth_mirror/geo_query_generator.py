import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

class GeoQueryGenerator:
    """
    Generates targeted queries (News, Official, Regional) for geopolitical claims.
    As per architecture specifications, it attempts to use Ollama (qwen2.5:3b) to generate
    exactly 3 search queries per sub-claim. If Ollama fails, it uses deterministic fallbacks.
    """
    def __init__(
        self,
        ollama_base_url: str = None,
        model: str = None,
        timeout: int = 15
    ):
        self.ollama_base_url = ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self.timeout = timeout

    def generate(self, sub_claim: str, involved_parties: list[str], claim_subtype: str) -> list[str]:
        """
        Uses Ollama to generate exactly 3 search queries:
        1. News query
        2. Official query
        3. Regional query
        Returns a list of 3 strings.
        """
        parties_str = ", ".join(involved_parties) if involved_parties else "Unknown"
        
        prompt = f"""You are a geopolitical intelligence search query generator.
Given a sub-claim, involved parties, and claim subtype, generate exactly 3 distinct search queries to retrieve maximum relevant information.
Return ONLY a JSON array of 3 strings. No markdown formatting, no explanations.

Queries must strictly follow this structure:
1. A general international news query
2. An official statement or government document query
3. A regional/local perspective query

Input Data:
Sub-claim: {sub_claim}
Involved Parties: {parties_str}
Claim Subtype: {claim_subtype}

Output JSON Array of 3 strings:
"""
        try:
            url = f"{self.ollama_base_url.rstrip('/')}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_predict": 150
                }
            }
            
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            response_text = data.get("response", "").strip()
            
            # Extract queries
            queries = json.loads(response_text)
            
            # Ensure we always get exactly 3 queries
            if isinstance(queries, list) and len(queries) >= 3:
                return [str(q).strip() for q in queries[:3]]
            elif isinstance(queries, list) and len(queries) > 0:
                base = [str(q).strip() for q in queries]
                base.extend(self._get_fallback_queries(sub_claim, involved_parties))
                return base[:3]
            else:
                logger.warning("Ollama returned invalid query format. Using fallback queries.")
                return self._get_fallback_queries(sub_claim, involved_parties)
                
        except Exception as e:
            logger.error(f"Ollama query generation failed: {e}. Using deterministic fallbacks.")
            return self._get_fallback_queries(sub_claim, involved_parties)

    def _get_fallback_queries(self, sub_claim: str, involved_parties: list[str]) -> list[str]:
        """Deterministic fallback queries."""
        q1 = f"{sub_claim} international news"
        
        parties = " ".join(involved_parties) if involved_parties else ""
        q2 = f"official statement {parties} {sub_claim}".strip()
        
        # Add a regional slant if there are parties
        primary_party = involved_parties[0] if involved_parties else "regional"
        q3 = f"local media perspective {primary_party} {sub_claim}".strip()
        
        return [q1, q2, q3]
