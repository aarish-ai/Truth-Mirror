import json
import os
import logging
from typing import List

from truth_mirror.models import ClaimContext, Entity

logger = logging.getLogger(__name__)

class ContextTracker:
    """Tracks narrative history of claims to identify repeated patterns or related claims."""
    
    def __init__(self, history_file: str = ".tm_narrative_history.json"):
        self.history_file = history_file
        self.history = self._load_history()

    def _load_history(self) -> list:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load narrative history: {e}")
                return []
        return []

    def _save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save narrative history: {e}")

    def track_claim(self, claim: str, entities: List[Entity]) -> ClaimContext:
        """Records a new claim and its entities, returning context from history."""
        related_claims = []
        entity_uris = {e.uri for e in entities if e.uri}
        
        # Find related claims in history
        for past_record in reversed(self.history):
            past_uris = set(past_record.get("entities", []))
            if entity_uris.intersection(past_uris):
                # Avoid adding the exact same claim multiple times as related context
                past_claim = past_record["claim"]
                if past_claim != claim and past_claim not in related_claims:
                    related_claims.append(past_claim)
        
        # Limit to top 5 recent related claims
        related_claims = related_claims[:5]
        
        # Add the current claim to history
        self.history.append({
            "claim": claim,
            "entities": list(entity_uris)
        })
        
        # Keep history size bounded
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
            
        self._save_history()
        
        # Generate summary
        if related_claims:
            bg_info = f"Found {len(related_claims)} recent claim(s) involving the same entities."
        else:
            bg_info = "No recent narrative context found for these entities."
            
        return ClaimContext(
            entities=entities,
            previous_claims=related_claims,
            background_summary=bg_info
        )
