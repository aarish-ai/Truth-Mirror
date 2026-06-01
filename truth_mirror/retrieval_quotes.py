import requests
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

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
            response = requests.get(self.endpoint_url, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("query", {}).get("search", [])
            return [{"source": "Wikiquote", "title": res["title"], "snippet": res["snippet"]} for res in results]
        except Exception as e:
            logger.error(f"Error querying Wikiquote: {e}")
            return [{"source": "Wikiquote", "error": str(e), "fallback": "semantic"}]

class MillerCenterConnector:
    def search_presidential_speeches(self, president: str, query: str) -> List[Dict[str, str]]:
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
