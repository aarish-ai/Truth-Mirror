"""News and Current Events retrieval connectors."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from truth_mirror.models import EvidenceItem
from truth_mirror.caching import EvidenceCache


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
            req = urllib.request.Request(api_url, headers={"User-Agent": "TruthMirror/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
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

        return items


class RSSAggregator:
    """Fetches news from standard RSS feeds based on query keywords."""

    def __init__(self, cache: EvidenceCache | None = None, max_results: int = 5):
        self.cache = cache
        self.max_results = max_results
        self.timeout_seconds = 10
        # Example feeds, could be expanded
        self.feeds = [
            ("BBC News", "http://feeds.bbci.co.uk/news/rss.xml"),
            ("NPR", "https://feeds.npr.org/1001/rss.xml"),
        ]

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
                req = urllib.request.Request(url, headers={"User-Agent": "TruthMirror/1.0"})
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    xml_bytes = response.read()
                root = ET.fromstring(xml_bytes)
            except Exception:
                continue

            for node in root.findall("./channel/item"):
                title = (node.findtext("title") or "").strip()
                description = (node.findtext("description") or "").strip()
                link = (node.findtext("link") or "").strip()
                pub_date = (node.findtext("pubDate") or datetime.now(timezone.utc).date().isoformat()).strip()

                if not title or not link:
                    continue

                text_to_search = f"{title} {description}".lower()
                
                # Check if any query term matches the article
                if not query_terms or any(term in text_to_search for term in query_terms):
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
            req = urllib.request.Request(api_url, headers={"User-Agent": "TruthMirror/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                xml_bytes = response.read()
            root = ET.fromstring(xml_bytes)
        except Exception:
            return []

        items: list[EvidenceItem] = []
        for node in root.findall("./channel/item")[:self.max_results]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            description = (node.findtext("description") or "").strip()
            pub_date = (node.findtext("pubDate") or datetime.now(timezone.utc).date().isoformat()).strip()
            
            if not title or not link:
                continue
                
            items.append(
                EvidenceItem(
                    source_title=title,
                    source_type="news",
                    publisher="Google News",
                    date=pub_date,
                    url_or_id=link,
                    excerpt=description[:500],
                    language="en",
                    independence_key="news:google_news",
                )
            )
            
        return items
