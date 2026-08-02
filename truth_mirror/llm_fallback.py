import os
import time
import json
import logging
import random
import re
import requests
from typing import List, Dict, Any, Optional

from truth_mirror.run_tracker import tracker
from truth_mirror.utils import strip_markdown_json
from truth_mirror.key_rotator import get_current_key, rotate_gemini_key
from truth_mirror.groq_router import call_groq_with_key_rotation

logger = logging.getLogger(__name__)

try:
    from json_repair import repair_json
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False


class LLMFallbackChain:
    """Consolidated utility for calling LLMs with fallbacks."""
    
    def __init__(self, sequence: List[str], models: Dict[str, str], tracker_module: str, temperature: float = 0.1, max_tokens: int = 4096):
        """
        sequence: list of providers to try, e.g., ["gemini", "groq", "openrouter"]
        models: dict mapping provider to model name, e.g., {"gemini": "gemini-3.5-flash"}
        """
        self.sequence = sequence
        self.models = models
        self.tracker_module = tracker_module
        self.temperature = temperature
        self.max_tokens = max_tokens
        
    def _parse_json(self, content: str) -> Optional[Any]:
        content = strip_markdown_json(content)
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match and content.strip().startswith('['):
             content = match.group(0)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            if JSON_REPAIR_AVAILABLE:
                repaired = repair_json(content, return_objects=True)
                if repaired:
                    return repaired
            return None

    def _call_groq(self, prompt: str) -> Optional[Any]:
        model = self.models.get("groq")
        if not model: return None
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_tokens
        }
        
        content, status = call_groq_with_key_rotation(payload=payload, timeout=60, log_prefix=f"[{self.tracker_module}]")
        if status == "success" and content:
            parsed = self._parse_json(content)
            if parsed is not None:
                tracker.record(self.tracker_module, model, "groq", "success")
                return parsed
        
        tracker.record(self.tracker_module, model, "groq", "failed")
        return None

    def _call_gemini(self, prompt: str) -> Optional[Any]:
        model = self.models.get("gemini", "gemini-2.5-flash")
        gemini_payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
                "maxOutputTokens": self.max_tokens
            }
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                api_key = get_current_key()
                if not api_key:
                    break
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                
                response = requests.post(url, json=gemini_payload, headers={"Content-Type": "application/json"}, timeout=30)
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + 1
                    logger.warning(f"[{self.tracker_module}] Gemini Rate limited. Waiting {wait_time}s.")
                    rotate_gemini_key()
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                resp_data = response.json()
                
                if resp_data.get("candidates") and resp_data["candidates"][0].get("content", {}).get("parts"):
                    content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = self._parse_json(content)
                    if parsed is not None:
                        tracker.record(self.tracker_module, model, "gemini", "success")
                        return parsed
                
                break
            except Exception as e:
                logger.warning(f"[{self.tracker_module}] Gemini attempt {attempt+1} failed: {e}")
                
        tracker.record(self.tracker_module, model, "gemini", "failed")
        return None

    def _call_openrouter(self, prompt: str) -> Optional[Any]:
        model = self.models.get("openrouter", "qwen/qwen3-next-80b-a3b-instruct:free")
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key or api_key == "your_openrouter_api_key_here":
            return None
            
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"}
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://truthmirror.app",
            "X-Title": "Truth Mirror"
        }
        
        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=40)
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                resp_data = response.json()
                content = resp_data["choices"][0]["message"]["content"]
                parsed = self._parse_json(content)
                if parsed is not None:
                    tracker.record(self.tracker_module, model, "openrouter", "success")
                    return parsed
                break
            except Exception as e:
                logger.warning(f"[{self.tracker_module}] OpenRouter attempt {attempt+1} failed: {e}")
                
        tracker.record(self.tracker_module, model, "openrouter", "failed")
        return None
        
    def execute(self, prompt: str) -> Optional[Any]:
        for provider in self.sequence:
            if provider == "groq":
                res = self._call_groq(prompt)
                if res is not None: return res
            elif provider == "gemini":
                res = self._call_gemini(prompt)
                if res is not None: return res
            elif provider == "openrouter":
                res = self._call_openrouter(prompt)
                if res is not None: return res
        
        tracker.record(self.tracker_module, "ALL_FAILED", "none", "failed")
        return None
