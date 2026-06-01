import os
import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class LLMClient:
    """
    A client that wraps the local Ollama HTTP API and falls back to Gemini
    if GEMINI_API_KEY is present and the local request fails.
    """
    def __init__(
        self, 
        ollama_url: str = "http://localhost:11434/api", 
        ollama_model: str = "llama3", 
        gemini_model: str = "gemini-1.5-flash"
    ):
        self.ollama_url = ollama_url.rstrip('/')
        self.ollama_model = ollama_model
        self.gemini_model = gemini_model
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

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
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse Gemini response: {data}")
            raise ValueError(f"Invalid Gemini response format: {e}")

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
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            gemini_role = "model" if role == "assistant" else "user"
            
            contents.append({
                "role": gemini_role,
                "parts": [{"text": content}]
            })
            
        payload = {"contents": contents}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse Gemini response: {data}")
            raise ValueError(f"Invalid Gemini response format: {e}")

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
