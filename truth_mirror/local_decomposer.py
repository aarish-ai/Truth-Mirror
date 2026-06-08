import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

class LocalDecomposer:
    def __init__(
        self,
        ollama_base_url: str = None,
        model: str = None,
        timeout: int = 15
    ):
        self.ollama_base_url = ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self.timeout = timeout

    def decompose(self, claim: str) -> list[str]:
        prompt = f"""Break this claim into simple sub-claims, separating temporal elements from core factual elements.
Return ONLY a JSON array of strings. No explanation. No markdown.

Ensure the temporal context evaluates the truthfulness for that specific date. Explicitly note if the action is currently ongoing versus historical, making it a "tense-aware" decomposition.

Example input: "Donald Trump is president of USA in June 2026"
Example output: ["Donald Trump is president of the USA", "The period in question is June 2026"]

Example input: "Donald Trump was president in July 2016"
Example output: ["Donald Trump is president of the USA", "The period in question is July 2016"]

Example input: "A war is happening today"
Example output: ["A war is happening", "The action is currently ongoing"]

Claim: "{claim}"

Output:"""
        
        try:
            url = f"{self.ollama_base_url.rstrip('/')}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_predict": 200
                }
            }
            
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            response_text = data.get("response", "").strip()
            
            # Strip markdown code fences if present
            if response_text.startswith("```"):
                lines = response_text.splitlines()
                if len(lines) >= 2:
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip().startswith("```"):
                        lines = lines[:-1]
                    response_text = "\n".join(lines).strip()
            
            subclaims = json.loads(response_text)
            
            # Validation
            if not isinstance(subclaims, list):
                raise ValueError("Response is not a JSON array")
                
            if not subclaims:
                raise ValueError("Empty list")
                
            if len(subclaims) > 6:
                raise ValueError("List length exceeds 6")
                
            valid_subclaims = []
            for item in subclaims:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError("Element is not a non-empty string")
                
                item = item.strip()
                # Condition: Relaxed length validation
                if len(item) >= len(claim) * 2 and len(subclaims) <= 1:
                    raise ValueError("Single element is significantly longer than the original claim")
                    
                valid_subclaims.append(item)
                
            return valid_subclaims
            
        except Exception as e:
            logger.warning(f"Failed to decompose claim: {e}")
            return [claim]
