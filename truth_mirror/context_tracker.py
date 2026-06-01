import json
import os
import logging
import time
from collections import Counter
from typing import List

from truth_mirror.models import ClaimContext, Entity

try:
    from sentence_transformers import SentenceTransformer, util
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

logger = logging.getLogger(__name__)

class ContextTracker:
    """Tracks narrative history of claims to identify repeated patterns or related claims."""
    
    def __init__(self, history_file: str = ".tm_narrative_history.json"):
        self.history_file = history_file
        self.history = self._load_history()
        
        self.model = None
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                logger.warning(f"Could not load SentenceTransformer: {e}")

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

    def record_verdict(self, claim: str, verdict: str):
        """Update the most recent matching claim with its final verdict."""
        for record in reversed(self.history):
            if record["claim"] == claim:
                record["verdict"] = verdict
                self._save_history()
                break

    def track_claim(self, claim: str, entities: List[Entity]) -> ClaimContext:
        """Records a new claim and its entities, returning context from history."""
        related_claims = []
        entity_uris = {e.uri for e in entities if e.uri}
        
        current_time = time.time()
        sixty_mins = 60 * 60
        variants_in_60m = 0
        past_records_for_entities = []
        
        # Find related claims in history
        for past_record in reversed(self.history):
            past_uris = set(past_record.get("entities", []))
            if entity_uris.intersection(past_uris):
                past_records_for_entities.append(past_record)
                past_claim = past_record["claim"]
                if past_claim != claim and past_claim not in related_claims:
                    related_claims.append(past_claim)
                
                past_time = past_record.get("timestamp", 0)
                if current_time - past_time <= sixty_mins:
                    variants_in_60m += 1
        
        # 1. Narrative engineering detection
        narrative_engineering_flag = variants_in_60m >= 3 # Plus current claim = 4+ variants
        
        # 2. Semantic similarity & claim mutation
        claim_mutation_flag = False
        differing_verdicts = set()
        
        if self.model is not None and related_claims:
            try:
                claim_emb = self.model.encode(claim)
                past_embs = self.model.encode(related_claims)
                sims = util.cos_sim(claim_emb, past_embs)[0]
                
                similar_claims = []
                for i, sim in enumerate(sims):
                    if sim.item() > 0.75:
                        similar_claims.append(related_claims[i])
                        
                if similar_claims:
                    for rec in past_records_for_entities:
                        if rec["claim"] in similar_claims and rec.get("verdict"):
                            differing_verdicts.add(rec["verdict"])
                    
                    if len(differing_verdicts) > 1:
                        claim_mutation_flag = True
            except Exception as e:
                logger.warning(f"Error computing semantic similarity: {e}")

        # 3. Narrative coherence score
        all_past_verdicts = [r.get("verdict") for r in past_records_for_entities if r.get("verdict")]
        narrative_coherence_score = 1.0
        if all_past_verdicts:
            c = Counter(all_past_verdicts)
            most_common_count = c.most_common(1)[0][1]
            narrative_coherence_score = most_common_count / len(all_past_verdicts)
        elif past_records_for_entities:
            narrative_coherence_score = 0.5
            
        # Add the current claim to history
        self.history.append({
            "claim": claim,
            "entities": list(entity_uris),
            "timestamp": current_time,
            "verdict": None
        })
        
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
            
        self._save_history()
        
        related_claims = related_claims[:5]
        
        bg_info_parts = []
        if related_claims:
            bg_info_parts.append(f"Found {len(related_claims)} recent claim(s) involving the same entities.")
        else:
            bg_info_parts.append("No recent narrative context found for these entities.")
            
        if narrative_engineering_flag:
            bg_info_parts.append("WARNING: Narrative engineering detected (4+ variants of same entity claim within 60 min).")
            
        if claim_mutation_flag:
            bg_info_parts.append(f"WARNING: Claim mutation detected (semantically similar claims >0.75 have differing past verdicts: {', '.join(differing_verdicts)}).")
            
        bg_info = " ".join(bg_info_parts)
            
        context = ClaimContext(
            entities=entities,
            previous_claims=related_claims,
            background_summary=bg_info,
            narrative_coherence_score=narrative_coherence_score
        )
        return context
