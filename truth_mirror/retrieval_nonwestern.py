import feedparser
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class NonWesternRSSConnector:
    def __init__(self, source_name: str, feed_url: str, perspective_label: str):
        self.source_name = source_name
        self.feed_url = feed_url
        self.perspective_label = perspective_label

    def fetch_recent_articles(self) -> List[Dict[str, str]]:
        try:
            feed = feedparser.parse(self.feed_url)
            results = []
            for entry in feed.entries[:10]:
                results.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                    "source": self.source_name,
                    "perspective_label": self.perspective_label
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching RSS for {self.source_name}: {e}")
            return []

class AlJazeeraConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "Middle Eastern / Qatari State-Funded")

class CGTNConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("CGTN", "https://www.cgtn.com/rss", "Chinese State Media")

class TASSConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("TASS", "https://tass.com/rss/v2.xml", "Russian State Media")

class XinhuaConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Xinhua", "http://www.xinhuanet.com/english/rss/world.xml", "Chinese State Media")

class DawnPKConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Dawn PK", "https://www.dawn.com/feeds/home", "Pakistani Media")

class MiddleEastEyeConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Middle East Eye", "https://www.middleeasteye.net/rss", "Middle Eastern Independent/Qatari-linked")

class PressTVConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Press TV", "https://www.presstv.ir/rss", "Iranian State Media")

class TehranTimesConnector(NonWesternRSSConnector):
    def __init__(self):
        super().__init__("Tehran Times", "https://www.tehrantimes.com/rss", "Iranian State-Affiliated")
