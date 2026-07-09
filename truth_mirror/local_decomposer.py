import os
import json
import logging
import requests
import re
import time
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

logger = logging.getLogger(__name__)

class LocalDecomposer:
    def __init__(
        self,
        ollama_base_url: str = None,
        model: str = None,
        timeout: int = 120
    ):
        self.ollama_base_url = ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self.timeout = timeout

    def decompose(self, claim: str) -> list[str]:
        prompt = f"""Break this claim into simple sub-claims, separating temporal elements from core factual elements.
Return ONLY a JSON array. Do not wrap it in a JSON object. Do not include markdown formatting or conversational text.

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
                            logger.warning(f"[LocalDecomposer] Rate limited on attempt {attempt+1}. Waiting {wait_time}s before retry.")
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
                        "num_predict": 200
                    }
                }
                
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                
                data = response.json()
                response_text = data.get("response", "").strip()
            
            subclaims = []
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if isinstance(v, list):
                            subclaims = v
                            break
                elif isinstance(parsed, list):
                    subclaims = parsed
            except Exception:
                start = response_text.find('[')
                end = response_text.rfind(']')
                if start != -1 and end != -1 and end > start:
                    try:
                        subclaims = json.loads(response_text[start:end+1])
                    except Exception:
                        pass
            
            if not subclaims:
                raise ValueError("Response is not a valid JSON array or could not be parsed")
            
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
            logger.info(f"Fallback to original claim (decomposition failed): {e}")
            return [claim]
