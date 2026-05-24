import os
import requests
import time
from bs4 import BeautifulSoup
import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleFactCheckConnector:
    """Connects to Google Fact Check Tools API."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    def search_claims(self, query: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("No Google API key provided. Using mock fallback for Google Fact Check.")
            return self._mock_fallback(query)
            
        params = {"query": query, "key": self.api_key}
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("claims", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying Google Fact Check API: {e}. Using mock fallback.")
            return self._mock_fallback(query)

    def _mock_fallback(self, query: str) -> List[Dict[str, Any]]:
        return [
            {
                "text": f"Mock claim related to: {query}",
                "claimant": "Mock Claimant",
                "claimDate": "2023-01-01T00:00:00Z",
                "claimReview": [
                    {
                        "publisher": {"name": "Mock Fact Checker", "site": "mockfactcheck.com"},
                        "url": "https://mockfactcheck.com/review",
                        "title": f"Mock Review of {query}",
                        "reviewDate": "2023-01-02T00:00:00Z",
                        "textualRating": "Mostly False",
                        "languageCode": "en"
                    }
                ]
            }
        ]

class SnopesFactCheckScraper:
    """Polite scraper for Snopes fact checks."""
    def __init__(self):
        self.base_url = "https://www.snopes.com/search/"
        # Use a realistic user agent to be polite and avoid basic blocking
        self.headers = {
            "User-Agent": "TruthMirror-ResearchBot/1.0 (Mozilla/5.0 Windows NT 10.0)"
        }

    def search(self, query: str) -> List[Dict[str, str]]:
        # Respectful scraping: brief pause
        time.sleep(1.0)
        
        try:
            # Snopes search results
            search_url = f"{self.base_url}?q={requests.utils.quote(query)}"
            response = requests.get(search_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            results = []
            
            # Generic extraction of titles and links
            for article in soup.find_all("article")[:5]: # Limit to top 5
                title_tag = article.find("h2") or article.find("h3")
                link_tag = article.find("a")
                
                if title_tag and link_tag:
                    results.append({
                        "title": title_tag.get_text(strip=True),
                        "url": link_tag.get("href", ""),
                        "source": "Snopes"
                    })
                    
            if not results:
                logger.info("No direct HTML results found on Snopes. Returning mock response.")
                return self._mock_fallback(query)
                
            return results
        except Exception as e:
            logger.error(f"Error scraping Snopes: {e}")
            return self._mock_fallback(query)
            
    def _mock_fallback(self, query: str) -> List[Dict[str, str]]:
         return [{"title": f"Snopes analysis: Is '{query}' true?", "url": "https://www.snopes.com/mock", "source": "Snopes"}]

class WorldBankConnector:
    """Connects to World Bank Open Data API."""
    def __init__(self):
        self.base_url = "http://api.worldbank.org/v2"

    def get_indicator_data(self, country_code: str, indicator: str, date: str = "2010:2020") -> List[Dict[str, Any]]:
        """
        Fetch indicator data.
        Example indicator: SP.POP.TOTL (Total Population)
        """
        url = f"{self.base_url}/country/{country_code}/indicator/{indicator}"
        params = {
            "format": "json",
            "date": date,
            "per_page": 100
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if len(data) > 1:
                return data[1] # The first element is pagination info, second is data
            return []
        except Exception as e:
            logger.error(f"Error querying World Bank API: {e}")
            return []

class FREDConnector:
    """Connects to Federal Reserve Economic Data (FRED) API."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        self.base_url = "https://api.stlouisfed.org/fred"

    def get_series_observations(self, series_id: str) -> List[Dict[str, str]]:
        if not self.api_key:
            logger.warning("No FRED API key provided. Using mock fallback for FRED.")
            return self._mock_fallback(series_id)

        url = f"{self.base_url}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json"
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("observations", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying FRED API: {e}. Using mock fallback.")
            return self._mock_fallback(series_id)

    def _mock_fallback(self, series_id: str) -> List[Dict[str, str]]:
        return [
            {"date": "2023-01-01", "value": "100.0"},
            {"date": "2023-02-01", "value": "101.5"}
        ]

class WikidataConnector:
    """Connects to Wikidata SPARQL endpoint."""
    def __init__(self):
        self.endpoint_url = "https://query.wikidata.org/sparql"

    def query(self, sparql_query: str) -> List[Dict[str, Any]]:
        # Require a valid user agent as per Wikidata policy
        headers = {
            "User-Agent": "TruthMirror/1.0 (https://github.com/example/truth_mirror; user@example.com)",
            "Accept": "application/sparql-results+json"
        }
        try:
            response = requests.get(self.endpoint_url, params={"query": sparql_query}, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("results", {}).get("bindings", [])
        except Exception as e:
            logger.error(f"Error querying Wikidata: {e}")
            return []
