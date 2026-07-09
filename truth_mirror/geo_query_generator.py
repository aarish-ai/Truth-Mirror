import os
import json
import re
import logging
import requests
import time
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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
        timeout: int = 120
    ):
        from datetime import datetime
        self.current_date_str = datetime.now().strftime("%d %B %Y")
        self.ollama_base_url = ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self.timeout = timeout

    def generate(self, sub_claim: str, involved_parties: list[str], claim_subtype: str) -> list[str]:
        if sub_claim.lower().startswith("the period in question") or sub_claim.lower().startswith("the action is currently"):
            return []
        """
        Uses Ollama to generate exactly 3 search queries:
        1. News query
        2. Official query
        3. Regional query
        Returns a list of 3 strings.
        """
        parties_str = ", ".join(involved_parties) if involved_parties else "Unknown"
        
        date_instruction = f"Today's date is {self.current_date_str}. Generate queries that prioritize the most recent reporting and events up to this date. For claims about recent or ongoing events, include date-scoped queries (e.g. \"Iran Israel June 2026\", \"Trump Iran strikes cancelled June 2026\").\n\n"
        prompt = date_instruction + f"""You are a geopolitical intelligence search query generator.
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
            response_text = None
            openrouter_failed = False
            
            if OPENROUTER_API_KEY:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://truthmirror.app",
                    "X-Title": "Truth Mirror"
                }
                payload = {
                    "model": "qwen/qwen3-next-80b-a3b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
                        if response.status_code == 429:
                            wait_time = (2 ** attempt) + 1
                            logger.warning(f"[GeoQueryGenerator] Rate limited on attempt {attempt+1}. Waiting {wait_time}s before retry.")
                            time.sleep(wait_time)
                            if attempt == max_retries - 1:
                                openrouter_failed = True
                            continue
                        response.raise_for_status()
                        response_text = response.json()["choices"][0]["message"]["content"]
                        openrouter_failed = False
                        break
                    except Exception as e:
                        logger.warning(f"OpenRouter failed ({e}), falling back to local Ollama.")
                        openrouter_failed = True
                        break
            else:
                logger.warning("OPENROUTER_API_KEY not set. Using local Ollama.")
                openrouter_failed = True
                
            if openrouter_failed:
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
            
            # Extract queries robustly
            queries = []
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if isinstance(v, list):
                            queries = v
                            break
                elif isinstance(parsed, list):
                    queries = parsed
            except Exception:
                start = response_text.find('[')
                end = response_text.rfind(']')
                if start != -1 and end != -1 and end > start:
                    try:
                        queries = json.loads(response_text[start:end+1])
                    except Exception:
                        pass
            
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
