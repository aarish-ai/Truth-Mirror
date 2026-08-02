"""News and Current Events retrieval connectors."""

from __future__ import annotations

import json
import urllib.parse
import defusedxml.ElementTree as ET
import requests
from datetime import datetime, timezone
import dateutil.parser

from truth_mirror.models import EvidenceItem
from truth_mirror.caching import EvidenceCache
import os
import logging

logger = logging.getLogger(__name__)

RSS_FEEDS_PATH = os.path.join(os.path.dirname(__file__), "rss_feeds.json")
try:
    with open(RSS_FEEDS_PATH, "r", encoding="utf-8") as _f:
        RSS_FEEDS = json.load(_f)
except Exception as e:
    logger.warning(f"Could not load RSS feeds from {RSS_FEEDS_PATH}: {e}")
    RSS_FEEDS = []

class GDELTConnector:
    """Connects to the GDELT DOC 2.0 API to find global news coverage."""

    def __init__(self, cache: EvidenceCache | None = None, max_results: int = 5):
        self.cache = cache
        self.max_results = max_results
        self.timeout_seconds = 10

    def retrieve(self, query: str) -> list[EvidenceItem]:
        cache_key = f"gdelt:{query.strip().lower()}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return [EvidenceItem(**item) for item in cached]

        api_url = (
            "https://api.gdeltproject.org/api/v2/doc/doc?"
            + urllib.parse.urlencode({
                "query": query,
                "mode": "artlist",
                "maxrecords": self.max_results,
                "format": "json"
            })
        )

        try:
            logger.info(f"[GDELTConnector] Querying: {query}")
            response = requests.get(api_url, headers={"User-Agent": "TruthMirror/1.0"}, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.warning(f"[GDELTConnector] Failed for query '{query}': {e}")
            return []

        items: list[EvidenceItem] = []
        for article in payload.get("articles", []):
            url = article.get("url", "")
            if not url:
                continue
            
            title = article.get("title", "")
            domain = article.get("domain", "unknown")
            date_str = str(article.get("seendate", ""))
            
            # GDELT date format: YYYYMMDDTHHMMSSZ
            try:
                dt = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                formatted_date = dt.date().isoformat()
            except ValueError:
                formatted_date = datetime.now(timezone.utc).date().isoformat()

            items.append(
                EvidenceItem(
                    source_title=title,
                    source_type="journalism",
                    publisher=domain,
                    date=formatted_date,
                    url_or_id=url,
                    excerpt=f"GDELT Match from {domain}",
                    language=article.get("language", "en"),
                    independence_key=f"news:{domain}",
                )
            )

        if self.cache:
            from dataclasses import asdict
            self.cache.set(cache_key, [asdict(item) for item in items])

        logger.info(f"[GDELTConnector] Retrieved {len(items)} items for: {query}")
        return items


class RSSAggregator:
    """Fetches news from standard RSS feeds based on query keywords."""

    def __init__(self, cache: EvidenceCache | None = None, max_results: int = 5):
        self.cache = cache
        self.max_results = max_results
        self.timeout_seconds = 10
        self.feeds = RSS_FEEDS

    def retrieve(self, query: str) -> list[EvidenceItem]:
        cache_key = f"rss:{query.strip().lower()}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return [EvidenceItem(**item) for item in cached]

        query_terms = set(word.lower() for word in query.split() if len(word) > 3)
        items: list[EvidenceItem] = []

        for publisher, url in self.feeds:
            try:
                logger.info(f"[RSSAggregator] Querying {publisher}: {query}")
                response = requests.get(url, headers={"User-Agent": "TruthMirror/1.0"}, timeout=self.timeout_seconds)
                response.raise_for_status()
                xml_bytes = response.content
                root = ET.fromstring(xml_bytes)
            except Exception as e:
                logger.warning(f"[RSSAggregator] Failed for query '{query}' from {publisher}: {e}")
                continue

            for node in root.findall("./channel/item"):
                title = (node.findtext("title") or "").strip()
                description = (node.findtext("description") or "").strip()
                link = (node.findtext("link") or "").strip()
                pub_date = (node.findtext("pubDate") or datetime.now(timezone.utc).date().isoformat()).strip()
                try:
                    pub_date = dateutil.parser.parse(pub_date).date().isoformat()
                except Exception:
                    pass

                if not title or not link:
                    continue

                text_to_search = f"{title} {description}".lower()
                
                # Check if any query term matches the article
                import re
                if not query_terms or any(re.search(rf'\b{re.escape(term)}\b', text_to_search, re.IGNORECASE) for term in query_terms):
                    items.append(
                        EvidenceItem(
                            source_title=title,
                            source_type="journalism",
                            publisher=publisher,
                            date=pub_date,
                            url_or_id=link,
                            excerpt=description[:500],
                            language="en",
                            independence_key=f"news:{publisher.lower()}",
                        )
                    )
                    
                    if len(items) >= self.max_results:
                        break
            if len(items) >= self.max_results:
                break

        if self.cache:
            from dataclasses import asdict
            self.cache.set(cache_key, [asdict(item) for item in items])

        logger.info(f"[RSSAggregator] Retrieved {len(items)} items for: {query}")
        return items

class BaseConnector:
    """Base interface for all connectors."""
    pass

class GoogleNewsRSSConnector(BaseConnector):
    """Fetches real-time news from Google News RSS feed."""
    def __init__(self, max_results: int = 8):
        self.max_results = max_results
        self.timeout_seconds = 10

    def search(self, query: str) -> list[EvidenceItem]:
        return self.retrieve(query)

    def retrieve(self, query: str) -> list[EvidenceItem]:
        api_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}"
        try:
            logger.info(f"[GoogleNewsRSSConnector] Querying: {query}")
            response = requests.get(api_url, headers={"User-Agent": "TruthMirror/1.0"}, timeout=self.timeout_seconds)
            response.raise_for_status()
            xml_bytes = response.content
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            logger.warning(f"[GoogleNewsRSSConnector] Failed for query '{query}': {e}")
            return []

        items: list[EvidenceItem] = []
        for node in root.findall("./channel/item")[:self.max_results]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            pub_date = (node.findtext("pubDate") or datetime.now(timezone.utc).date().isoformat()).strip()
            try:
                pub_date = dateutil.parser.parse(pub_date).date().isoformat()
            except Exception:
                pass
            
            if not title or not link:
                continue
                
            items.append(
                EvidenceItem(
                    source_title=title,
                    source_type="journalism",
                    publisher="Google News",
                    date=pub_date,
                    url_or_id=link,
                    excerpt=description[:500],
                    language="en",
                    independence_key=f"news:{urllib.parse.urlparse(link).netloc.replace('www.', '')}",
                )
            )
            
        logger.info(f"[GoogleNewsRSSConnector] Retrieved {len(items)} items for: {query}")
        return items
