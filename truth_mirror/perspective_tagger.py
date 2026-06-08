import json
import logging
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from truth_mirror.models import EvidenceItem

logger = logging.getLogger(__name__)

class PerspectiveTagger:
    """
    Determines the geopolitical perspective group for evidence items.
    Groups include: western_allied, state_media_X, non_western, neutral_intl, etc.
    """
    def __init__(self, registry_path: str = None):
        if registry_path is None:
            registry_path = Path(__file__).parent / "perspective_registry.json"
        
        self.registry = {}
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                self.registry = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load perspective registry from {registry_path}: {e}")

    def tag(self, evidence_list: List[EvidenceItem], involved_parties: List[str]) -> None:
        """
        Iterates over evidence items, determines their geopolitical perspective group
        based on the registry or publisher data, and updates the item's perspective_label.
        """
        for item in evidence_list:
            domain = self._extract_domain(item.url_or_id)
            if not domain:
                domain = item.publisher.lower()
                
            registry_entry = self.registry.get(domain)
            
            if registry_entry:
                perspective = registry_entry.get("perspective")
                if perspective:
                    item.perspective_label = self._map_to_group(perspective)
                    continue

            # Fallback logic if not found in registry
            item.perspective_label = self._fallback_tagging(item.publisher, involved_parties)
            
    def _extract_domain(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("http"):
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                return domain
            except Exception:
                return ""
        # If it looks like a domain
        if "." in url and " " not in url:
            return url.lower()
        return ""

    def _map_to_group(self, raw_perspective: str) -> str:
        raw = raw_perspective.lower()
        if raw in [
            "western_mainstream", 
            "liberal", 
            "conservative", 
            "liberal_leaning", 
            "conservative_leaning"
        ]:
            return "western_allied"
        elif raw == "neutral":
            return "neutral_intl"
        elif raw == "non_western":
            return "non_western"
        elif raw.startswith("state_sponsored_"):
            # e.g. state_sponsored_russia -> state_media_russia
            country = raw.split("state_sponsored_")[-1]
            return f"state_media_{country}"
        return "unknown"

    def _fallback_tagging(self, publisher: str, involved_parties: List[str]) -> str:
        pub = publisher.lower()
        if "rt " in pub or pub == "rt" or "sputnik" in pub:
            return "state_media_russia"
        if "cgtn" in pub or "xinhua" in pub or "global times" in pub:
            return "state_media_china"
        if "bbc" in pub or "cnn" in pub or "fox" in pub or "nytimes" in pub or "wsj" in pub:
            return "western_allied"
        if "reuters" in pub or "ap" in pub or "associated press" in pub:
            return "neutral_intl"
        if "al jazeera" in pub or "scmp" in pub:
            return "non_western"
        return "unknown"
