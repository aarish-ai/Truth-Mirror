import os
import requests
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def _is_test_mode() -> bool:
    return os.getenv("TM_TEST_MODE", "").lower() == "true"

class WaybackMachineConnector:
    def __init__(self):
        self.base_url = "http://archive.org/wayback/available"

    def get_archived_url(self, url: str, timestamp: str = None) -> Dict[str, Any]:
        params = {"url": url}
        if timestamp:
            params["timestamp"] = timestamp
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            return response.json().get("archived_snapshots", {})
        except Exception as e:
            logger.error(f"Error querying Wayback Machine: {e}")
            return {}

class OpenLibraryConnector:
    def __init__(self):
        self.base_url = "https://openlibrary.org/search.json"

    def search_books(self, query: str) -> List[Dict[str, Any]]:
        try:
            response = requests.get(self.base_url, params={"q": query, "limit": 5}, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("docs", [])
        except Exception as e:
            logger.error(f"Error querying Open Library: {e}")
            return []

