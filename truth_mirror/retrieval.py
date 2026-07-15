"""Hybrid retrieval with lightweight caching and multi-source connectors."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import logging

from truth_mirror.models import EvidenceItem

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievalConfig:
    max_results: int = 8
    timeout_seconds: int = 8


class EvidenceRetriever:
    CACHE_VERSION = "v2.4"

    def __init__(self, cache_path: str = ".tm_cache.json", config: RetrievalConfig | None = None):
        self.cache_file = Path(cache_path)
        self.config = config or RetrievalConfig()
        self._cache = self._load_cache()

    def _load_cache(self) -> dict[str, list[dict]]:
        if not self.cache_file.exists():
            return {}
        try:
            cache_data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            logger.info(f"Loaded {len(cache_data)} items from cache version {self.CACHE_VERSION}")
            return cache_data
        except json.JSONDecodeError:
            return {}

    def _save_cache(self) -> None:
        self.cache_file.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")

    def retrieve(self, query: str) -> list[EvidenceItem]:
        key = f"{self.CACHE_VERSION}:{query.strip().lower()}"
        if key in self._cache:
            return [self._normalize_cached_item(EvidenceItem(**item)) for item in self._cache[key]]
        results = (
            self._query_wikipedia(query)
            + self._query_wikinews(query)
            + self._query_crossref(query)
        )
        results = self._dedupe(results)
        self._cache[key] = [asdict(item) for item in results]
        self._save_cache()
        return results

    @staticmethod
    def _normalize_cached_item(item: EvidenceItem) -> EvidenceItem:
        publisher = item.publisher.strip().lower()
        if publisher == "wikipedia" and item.source_type == "other":
            item.source_type = "journalism"
            item.independence_key = item.independence_key or "wikipedia"
        if publisher == "wikinews" and item.source_type == "other":
            item.source_type = "journalism"
            item.independence_key = item.independence_key or "wikinews"
        if publisher == "crossref":
            item.source_type = "academic"
        return item

    def _dedupe(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        seen: set[str] = set()
        deduped: list[EvidenceItem] = []
        for item in evidence:
            key = (item.url_or_id or item.source_title).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _query_wikipedia(self, query: str) -> list[EvidenceItem]:
        search_url = (
            "https://en.wikipedia.org/w/api.php?"
            + urllib.parse.urlencode(
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "utf8": 1,
                    "format": "json",
                    "srlimit": self.config.max_results,
                }
            )
        )
        try:
            logger.info(f"[WikipediaConnector] Querying: {query}")
            req = urllib.request.Request(search_url, headers={"User-Agent": "TruthMirror/0.1"})
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"[WikipediaConnector] Failed for query '{query}': {e}")
            return []
        items: list[EvidenceItem] = []
        for result in payload.get("query", {}).get("search", []):
            title = result.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", result.get("snippet", "")).strip()
            page_url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            items.append(
                EvidenceItem(
                    source_title=title,
                    source_type="journalism",
                    publisher="Wikipedia",
                    date=datetime.now(timezone.utc).date().isoformat(),
                    url_or_id=page_url,
                    excerpt=snippet,
                    author="community",
                    language="en",
                    independence_key="wikipedia",
                )
            )
        logger.info(f"[WikipediaConnector] Retrieved {len(items)} items for: {query}")
        return items

    def _query_wikinews(self, query: str) -> list[EvidenceItem]:
        search_url = (
            "https://en.wikinews.org/w/api.php?"
            + urllib.parse.urlencode(
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "utf8": 1,
                    "format": "json",
                    "srlimit": self.config.max_results // 2,
                }
            )
        )
        try:
            logger.info(f"[WikinewsConnector] Querying: {query}")
            req = urllib.request.Request(search_url, headers={"User-Agent": "TruthMirror/0.2"})
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"[WikinewsConnector] Failed for query '{query}': {e}")
            return []

        items: list[EvidenceItem] = []
        for result in payload.get("query", {}).get("search", []):
            title = result.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", result.get("snippet", "")).strip()
            page_url = "https://en.wikinews.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            items.append(
                EvidenceItem(
                    source_title=title,
                    source_type="journalism",
                    publisher="Wikinews",
                    date=datetime.now(timezone.utc).date().isoformat(),
                    url_or_id=page_url,
                    excerpt=snippet[:500],
                    author="unknown",
                    language="en",
                    independence_key="wikinews",
                )
            )
        logger.info(f"[WikinewsConnector] Retrieved {len(items)} items for: {query}")
        return items

    def _query_crossref(self, query: str) -> list[EvidenceItem]:
        api_url = (
            "https://api.crossref.org/works?"
            + urllib.parse.urlencode({"query.title": query, "rows": self.config.max_results // 2})
        )
        try:
            logger.info(f"[CrossrefConnector] Querying: {query}")
            req = urllib.request.Request(api_url, headers={"User-Agent": "TruthMirror/0.2"})
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"[CrossrefConnector] Failed for query '{query}': {e}")
            return []

        items: list[EvidenceItem] = []
        for work in payload.get("message", {}).get("items", []):
            titles = work.get("title", [])
            title = titles[0] if titles else ""
            doi = work.get("DOI", "")
            link = f"https://doi.org/{doi}" if doi else ""
            year_parts = work.get("created", {}).get("date-parts", [[None]])
            year = year_parts[0][0]
            date = f"{year}-01-01" if isinstance(year, int) else datetime.now(timezone.utc).date().isoformat()
            container = work.get("container-title", [])
            publisher = (container[0] if container else "Crossref").strip() or "Crossref"
            if not title:
                continue
            items.append(
                EvidenceItem(
                    source_title=title,
                    source_type="academic",
                    publisher=publisher,
                    date=date,
                    url_or_id=link or work.get("URL", ""),
                    excerpt=(work.get("abstract") or "Academic metadata record from Crossref.")[:500],
                    author="unknown",
                    language="en",
                    independence_key=f"crossref:{publisher.lower()}",
                )
            )
        logger.info(f"[CrossrefConnector] Retrieved {len(items)} items for: {query}")
        return items

