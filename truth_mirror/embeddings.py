import json
import urllib.request
import urllib.error
import logging
from truth_mirror.key_rotator import get_current_key, rotate_gemini_key

logger = logging.getLogger(__name__)

from typing import Optional, List

def get_gemini_embedding(text: str) -> Optional[List[float]]:
    if not text:
        return None

    max_attempts = 5
    for attempt in range(max_attempts):
        api_key = get_current_key()
        if not api_key:
            logger.warning("[Embeddings] No Gemini API key available. Attempting rotation.")
            rotate_gemini_key()
            api_key = get_current_key()
            if not api_key:
                logger.warning("[Embeddings] Still no key after rotation. Returning None.")
                return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
        payload = {
            "content": {
                "parts": [
                    {"text": text}
                ]
            }
        }
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                embedding_values = resp_data.get("embedding", {}).get("values")
                if embedding_values:
                    return [float(val) for val in embedding_values]
                else:
                    logger.warning(f"[Embeddings] Response did not contain embedding: {resp_data}")
                    return None
        except urllib.error.HTTPError as e:
            if e.code in (429, 403):
                logger.warning(f"[Embeddings] HTTPError {e.code} on attempt {attempt+1}. Rotating key and retrying.")
                rotate_gemini_key()
                continue
            else:
                logger.error(f"[Embeddings] HTTPError {e.code}: {e.read().decode('utf-8', errors='ignore')}")
                return None
        except Exception as e:
            logger.error(f"[Embeddings] Exception in get_gemini_embedding: {e}")
            return None

    return None

def get_gemini_embeddings(texts: list[str]) -> list[Optional[list[float]]]:
    return [get_gemini_embedding(t) for t in texts]
