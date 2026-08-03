import os
import requests
import time
from bs4 import BeautifulSoup
import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _is_test_mode() -> bool:
    return os.getenv("TM_TEST_MODE", "").lower() == "true"


class GoogleFactCheckConnector:
    """Connects to Google Fact Check Tools API."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    def search_claims(self, query: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("API key missing for GoogleFactCheckConnector — skipping connector")
            return []
            
        params = {"query": query, "key": self.api_key}
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("claims", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying Google Fact Check API: {e}.")
            return []

class SnopesFactCheckScraper:
    """Polite scraper for Snopes fact checks."""
    def __init__(self):
        self.base_url = "https://www.snopes.com/search/"
        # Use a realistic user agent to be polite and avoid basic blocking
        self.headers = {
            "User-Agent": "TruthMirror-ResearchBot/1.0 (Mozilla/5.0 Windows NT 10.0)"
        }

    def search(self, query: str) -> List[Dict[str, str]]:
        try:
            # Snopes search results
            search_url = f"{self.base_url}?q={requests.utils.quote(query)}"
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            results = []
            
            # Generic extraction of titles and links
            for article in soup.find_all("article")[:5]: # Limit to top 5
                try:
                    title_tag = article.find(["h2", "h3"])
                    link_tag = article.find("a")
                    
                    if title_tag and link_tag:
                        title = title_tag.get_text(strip=True)
                        url = link_tag.get("href", "").strip()
                        
                        if not url:
                            continue
                            
                        if url.startswith("/"):
                            url = "https://www.snopes.com" + url
                            
                        if title and url:
                            results.append({
                                "title": title,
                                "url": url,
                                "source": "Snopes"
                            })
                except Exception as e:
                    logger.debug(f"Skipping malformed Snopes article: {e}")
                    
            if not results:
                logger.info("No direct HTML results found on Snopes.")
                return []
                
            return results
        except Exception as e:
            logger.error(f"Error scraping Snopes: {e}")
            return []

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
            response = requests.get(url, params=params, timeout=15)
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
            logger.warning("API key missing for FREDConnector — skipping connector")
            return []

        url = f"{self.base_url}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json"
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("observations", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying FRED API: {e}.")
            return []

class WikidataSPARQLConnector:
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
            response = requests.get(self.endpoint_url, params={"query": sparql_query}, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("results", {}).get("bindings", [])
        except Exception as e:
            logger.error(f"Error querying Wikidata: {e}")
            return []

class GovInfoConnector:
    """Connects to GovInfo API."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOVINFO_API_KEY")
        self.base_url = "https://api.govinfo.gov"

    def search_packages(self, query: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("API key missing for GovInfoConnector — skipping connector")
            return []
            
        url = f"{self.base_url}/search"
        params = {
            "query": query,
            "api_key": self.api_key,
            "pageSize": 5
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json().get("results", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying GovInfo: {e}")
            return []

