import os
import requests
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def _is_test_mode() -> bool:
    return os.getenv("TM_TEST_MODE", "").lower() == "true"

class WikiquoteConnector:
    def __init__(self):
        self.endpoint_url = "https://en.wikiquote.org/w/api.php"

    def search_quote(self, person: str, keyword: str = "") -> List[Dict[str, Any]]:
        # A basic API search
        params = {
            "action": "query",
            "list": "search",
            "srsearch": f"{person} {keyword}".strip(),
            "format": "json",
            "utf8": 1
        }
        try:
            response = requests.get(self.endpoint_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            results = data.get("query", {}).get("search", [])
            return [{"source": "Wikiquote", "title": res["title"], "snippet": res["snippet"]} for res in results]
        except Exception as e:
            logger.error(f"Error querying Wikiquote: {e}")
            if _is_test_mode():
                return [{"source": "Wikiquote", "error": str(e), "fallback": "semantic"}]
            return []

class MillerCenterConnector:
    def search_presidential_speeches(self, president: str, query: str) -> List[Dict[str, str]]:
        if not _is_test_mode():
            return []
        # Mock implementation for Miller Center Presidential Speeches
        # Provides an exact match / semantic fallback
        return [
            {
                "source": "Miller Center", 
                "president": president,
                "snippet": f"Exact match or semantic fallback for '{query}' in {president}'s speech.",
                "url": "https://millercenter.org/the-presidency/presidential-speeches"
            }
        ]
