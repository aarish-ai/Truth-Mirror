import logging
from typing import List
import urllib.parse
import urllib.request
import defusedxml.ElementTree as ET
from datetime import datetime, timezone
from truth_mirror.models import EvidenceItem

logger = logging.getLogger(__name__)

class NonWesternRSSConnector:
    def __init__(self, source_name: str, domain: str, perspective_label: str):
        self.source_name = source_name
        self.domain = domain
        self.perspective_label = perspective_label
        self.max_results = 8
        self.timeout_seconds = 10

    def search(self, query: str) -> list[EvidenceItem]:
        site_query = f"{query} site:{self.domain}"
        api_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(site_query)}"
        
        try:
            logger.info(f"[{self.source_name}Connector] Querying: {api_url}")
            req = urllib.request.Request(api_url, headers={"User-Agent": "TruthMirror/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                xml_bytes = response.read()
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            logger.warning(f"[{self.source_name}Connector] Failed for query '{query}': {e}")
            return []

        items = []
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
                    source_type="journalism",
                    publisher=self.source_name,
                    date=pub_date,
                    url_or_id=link,
                    excerpt=description[:500],
                    language="en",
                    independence_key=f"news:{self.domain.replace('.', '_')}",
                    perspective_label=self.perspective_label
                )
            )
            
        logger.info(f"[{self.source_name}Connector] Retrieved {len(items)} items for: {query}")
        return items

    def retrieve(self, query: str) -> list[EvidenceItem]:
        return self.search(query)

class AlJazeeraConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Al Jazeera", "aljazeera.com", "Middle Eastern / Qatari State-Funded")

class CGTNConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("CGTN", "cgtn.com", "Chinese State Media")

class TASSConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("TASS", "tass.com", "Russian State Media")

class XinhuaConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Xinhua", "xinhuanet.com", "Chinese State Media")

class DawnPKConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Dawn PK", "dawn.com", "Pakistani Media")

class MiddleEastEyeConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Middle East Eye", "middleeasteye.net", "Middle Eastern Independent/Qatari-linked")

class PressTVConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Press TV", "presstv.ir", "Iranian State Media")

class TehranTimesConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Tehran Times", "tehrantimes.com", "Iranian State-Affiliated")
