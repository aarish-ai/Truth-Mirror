import json
import logging
from typing import List, Dict, Set, Any, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HostileSourceTriangulator:
    """
    Implements Phase 5: Hostile-Source Triangulation.
    Identifies source stances and requires agreement across hostile/opposing
    sources for high-confidence verdicts on contested claims.
    """
    def __init__(self, ideology_map_path: str = None):
        self.ideology_map = self._load_ideology_map(ideology_map_path)
        
    def _load_ideology_map(self, ideology_map_path: str) -> Dict[str, str]:
        """
        Loads the source ideology map. Provides a mock if not specified or available.
        """
        import os
        if not ideology_map_path:
            default_path = os.path.join(os.path.dirname(__file__), "perspective_registry.json")
            if os.path.exists(default_path):
                ideology_map_path = default_path

        if ideology_map_path:
            try:
                with open(ideology_map_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Support both simple key-value and new structured registry
                if data and isinstance(next(iter(data.values())), dict):
                    return {k: v.get("perspective", "unknown") for k, v in data.items()}
                return data
            except Exception as e:
                logger.warning(f"Failed to load ideology map from {ideology_map_path}. Using mock map. Error: {e}")
        
        # Mock ideology map
        return {
            "foxnews.com": "conservative",
            "breitbart.com": "conservative",
            "wsj.com": "conservative_leaning",
            "cnn.com": "liberal",
            "msnbc.com": "liberal",
            "nytimes.com": "liberal_leaning",
            "reuters.com": "neutral",
            "apnews.com": "neutral",
            "bbc.com": "neutral",
            "aljazeera.com": "non_western",
            "rt.com": "state_sponsored_russia",
            "cgtn.com": "state_sponsored_china"
        }

    def _determine_source_stance(self, source_url: str) -> str:
        """
        Determines the stance/ideology of a given source.
        """
        # Basic domain extraction for mock matching
        domain = source_url.split("//")[-1].split("/")[0].replace("www.", "")
        
        # Exact match
        if domain in self.ideology_map:
            return self.ideology_map[domain]
            
        # Substring match (naive)
        for known_domain, stance in self.ideology_map.items():
            if known_domain in domain:
                return stance
                
        return "unknown"

    def _are_hostile_or_opposing(self, stances: Set[str]) -> bool:
        """
        Checks if a set of stances contains opposing or hostile ideologies.
        """
        if "unknown" in stances and len(stances) == 1:
            return False
            
        # Define opposing pairs/groups
        opposing_groups = [
            ({"conservative", "conservative_leaning"}, {"liberal", "liberal_leaning"}),
            ({"state_sponsored_russia", "state_sponsored_china", "non_western"}, {"conservative", "liberal", "neutral"}) # Western vs Non-western/State
        ]
        
        for group_a, group_b in opposing_groups:
            has_a = any(stance in group_a for stance in stances)
            has_b = any(stance in group_b for stance in stances)
            
            if has_a and has_b:
                return True
                
        return False

    def triangulate(self, claim: str, evidence: List[Any]) -> Tuple[bool, float, str]:
        """
        Evaluates a claim based on the triangulation of hostile/opposing sources.
        
        Returns:
            Tuple containing:
            - is_high_confidence (bool): True if verified across hostile lines.
            - confidence_score (float): 0.0 to 1.0 confidence score.
            - reasoning (str): Explanation of the triangulation result.
        """
        logger.info(f"Triangulating claim: '{claim[:50]}...'")
        
        supporting_sources = [e.url_or_id for e in evidence if e.stance == "supports" and e.url_or_id]
        contradicting_sources = [e.url_or_id for e in evidence if e.stance == "contradicts" and e.url_or_id]
        
        # Extract stances for both sides
        supporting_stances = {self._determine_source_stance(src) for src in supporting_sources}
        contradicting_stances = {self._determine_source_stance(src) for src in contradicting_sources}
        
        logger.debug(f"Supporting stances: {supporting_stances}")
        logger.debug(f"Contradicting stances: {contradicting_stances}")
        
        # Check for cross-ideological agreement on supporting the claim
        cross_support = self._are_hostile_or_opposing(supporting_stances)
        
        # Check for cross-ideological agreement on contradicting the claim
        cross_contradict = self._are_hostile_or_opposing(contradicting_stances)
        
        if cross_support and not cross_contradict:
            reasoning = "High confidence: Supported by hostile/opposing sources."
            return True, 0.9, reasoning
            
        if cross_contradict and not cross_support:
            reasoning = "High confidence (False): Contradicted by hostile/opposing sources."
            return True, 0.9, reasoning
            
        if cross_support and cross_contradict:
            reasoning = "Low confidence: Both support and contradiction observed across hostile lines. Highly contested."
            return False, 0.4, reasoning
            
        # No cross-ideological agreement
        if len(supporting_stances) > 0 and len(contradicting_stances) == 0:
            reasoning = "Medium-low confidence: Supported by sources, but lacks cross-ideological confirmation."
            return False, 0.6, reasoning
            
        if len(contradicting_stances) > 0 and len(supporting_stances) == 0:
            reasoning = "Medium-low confidence: Contradicted by sources, but lacks cross-ideological confirmation."
            return False, 0.6, reasoning
            
        reasoning = "Low confidence: Insufficient source diversity to triangulate."
        return False, 0.3, reasoning

if __name__ == '__main__':
    # Simple test
    triangulator = HostileSourceTriangulator()
    
    # Test case 1: Cross-ideological support
    claim1 = "The sky is blue."
    sources_supporting_1 = ["https://www.foxnews.com/story/1", "https://www.nytimes.com/article/1"]
    sources_contradicting_1 = []
    
    is_hc, score, reason = triangulator.triangulate(claim1, sources_supporting_1, sources_contradicting_1)
    print(f"Claim: {claim1}\\nResult: High Confidence={is_hc}, Score={score}, Reasoning={reason}\\n")
    
    # Test case 2: Echo chamber support
    claim2 = "Policy X is the best."
    sources_supporting_2 = ["https://www.foxnews.com/story/2", "https://www.breitbart.com/article/2"]
    sources_contradicting_2 = []
    
    is_hc, score, reason = triangulator.triangulate(claim2, sources_supporting_2, sources_contradicting_2)
    print(f"Claim: {claim2}\\nResult: High Confidence={is_hc}, Score={score}, Reasoning={reason}\\n")
