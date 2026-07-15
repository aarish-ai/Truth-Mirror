import os
import json
import logging
from truth_mirror.groq_router import GROQ_SIMPLE_MODEL, get_model_label, call_groq_with_key_rotation
import requests
import re
import time
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

logger = logging.getLogger(__name__)

class LocalDecomposer:
    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def decompose(self, claim: str) -> list[str]:
        prompt = f"""Break this claim into simple sub-claims, separating temporal elements from core factual elements.
Return ONLY a JSON array. Do not wrap it in a JSON object. Do not include markdown formatting or conversational text.

Ensure the decomposition is timeline-agnostic and does not contain specific dates, months, or years. Keep queries broad and neutral.

Example input: "Donald Trump is president of USA in the current era"
Example output: ["Donald Trump is president of the USA", "The period in question is the current era"]

Example input: "Donald Trump was president in a past term"
Example output: ["Donald Trump is president of the USA", "The period in question is a past term"]

Example input: "A war is happening today"
Example output: ["A war is happening", "The action is currently ongoing"]

Claim: "{claim}"

Output:"""
        
        def _call_groq(prompt_str: str) -> list | None:
            payload = {
                "model": GROQ_SIMPLE_MODEL,
                "messages": [{"role": "user", "content": prompt_str}],
                "temperature": 0.1,
                "max_tokens": 512
            }

            content, status = call_groq_with_key_rotation(
                payload=payload,
                timeout=25,
                log_prefix="[LocalDecomposer]"
            )

            if status != "success" or content is None:
                return None

            try:
                parsed = json.loads(content)
                logger.info("[LocalDecomposer] Groq call succeeded.")
                if isinstance(parsed, list):
                    return parsed
                for key in parsed:
                    if isinstance(parsed[key], list):
                        return parsed[key]
                return None
            except Exception as e:
                logger.warning(f"[LocalDecomposer] Failed to parse Groq response: {e}")
                return None

        try:
            response_text = None
            openrouter_failed = False
            
            logger.info(f"[LocalDecomposer] Attempting Groq ({get_model_label(GROQ_SIMPLE_MODEL)}) for claim decomposition.")
            groq_result = _call_groq(prompt)
            if groq_result is not None:
                # Format to JSON string so the rest of the parsing logic handles it uniformly
                response_text = json.dumps(groq_result)
            elif OPENROUTER_API_KEY:
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
                        logger.warning(f"OpenRouter failed ({e}).")
                        openrouter_failed = True
                        break
            if openrouter_failed:
                raise ValueError("OpenRouter API failed for decomposition.")
            
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
