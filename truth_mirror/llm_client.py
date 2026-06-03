import os
import logging
import requests
from typing import List, Dict, Any
try:
    from google import genai as google_genai
    from google.genai import types as genai_types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

class LLMClient:
    """
    A client that wraps the local Ollama HTTP API and falls back to Gemini
    if GEMINI_API_KEY is present and the local request fails.
    """
    def __init__(
        self, 
        ollama_url: str = None, 
        ollama_model: str = None, 
        gemini_model: str = None
    ):
        base_url = (ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip('/')
        if not base_url.endswith("/api"):
            base_url += "/api"
        self.ollama_url = base_url
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "gemma2:2b")
        self.gemini_model = gemini_model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self._genai_client = None
        if self.gemini_api_key and _GENAI_AVAILABLE:
            self._genai_client = google_genai.Client(api_key=self.gemini_api_key)

    def _ollama_complete(self, prompt: str) -> str:
        url = f"{self.ollama_url}/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("response", "")

    def _gemini_complete(self, prompt: str) -> str:
        if not self.gemini_api_key or not _GENAI_AVAILABLE or not self._genai_client:
            raise ValueError("Gemini SDK not available or GEMINI_API_KEY not set.")
        try:
            response = self._genai_client.models.generate_content(
                model=self.gemini_model,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Failed to generate Gemini response: {e}")
            raise ValueError(f"Gemini API Error: {e}")

    def complete(self, prompt: str) -> str:
        """
        Completes a single text prompt. Tries Ollama first, falls back to Gemini.
        """
        try:
            return self._ollama_complete(prompt)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama completion failed: {e}. Falling back to Gemini.")
            if self.gemini_api_key:
                return self._gemini_complete(prompt)
            else:
                logger.error("Ollama failed and GEMINI_API_KEY is not set.")
                raise Exception(f"Both Ollama and Gemini fallback failed. Original error: {e}")

    def _ollama_chat(self, messages: List[Dict[str, str]]) -> str:
        url = f"{self.ollama_url}/chat"
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "")

    def _gemini_chat(self, messages: List[Dict[str, str]]) -> str:
        if not self.gemini_api_key or not _GENAI_AVAILABLE or not self._genai_client:
            raise ValueError("Gemini SDK not available or GEMINI_API_KEY not set.")
        combined = "\n".join(m.get('content', '') for m in messages)
        try:
            response = self._genai_client.models.generate_content(
                model=self.gemini_model,
                contents=combined
            )
            return response.text
        except Exception as e:
            logger.error(f"Failed to chat with Gemini: {e}")
            raise ValueError(f"Gemini API Error: {e}")

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Chat completion using a list of message dicts (e.g. [{"role": "user", "content": "hi"}]).
        Tries Ollama first, falls back to Gemini.
        """
        try:
            return self._ollama_chat(messages)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama chat failed: {e}. Falling back to Gemini.")
            if self.gemini_api_key:
                return self._gemini_chat(messages)
            else:
                logger.error("Ollama failed and GEMINI_API_KEY is not set.")
                raise Exception(f"Both Ollama and Gemini fallback failed. Original error: {e}")
