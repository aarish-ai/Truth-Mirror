"""
Temporal validation - catch impossible/future dates early.
"""
from datetime import datetime
import re
from typing import Tuple

class TemporalValidator:
    """Validates temporal claims before evidence retrieval."""
    
    def __init__(self):
        self.current_year = datetime.now().year
        self.min_reasonable_year = 1000  # Nothing before medieval times makes sense for most modern claims.

    def validate(self, claim: str) -> Tuple[bool, str]:
        """
        Checks if the claim contains temporally impossible dates (e.g., future dates 
        or dates too far in the past).
        
        Args:
            claim (str): The text of the claim.
            
        Returns:
            Tuple[bool, str]: A tuple of (is_valid, reason).
        """
        # Find years using contextual keywords
        context_pattern = r'\b(?:in|year|since|from|until|during)\s+(\d{3,4})\b'
        for match in re.finditer(context_pattern, claim, re.IGNORECASE):
            year = int(match.group(1))
            if year > self.current_year:
                return False, f"The claim references a future year ({year}), which is impossible."
            if year < self.min_reasonable_year:
                return False, f"The claim references an impossibly old year ({year}) for this context."

        # Find standalone 4-digit years (1000-2999)
        standalone_pattern = r'\b(1\d{3}|2\d{3})\b'
        for match in re.finditer(standalone_pattern, claim):
            year = int(match.group(1))
            if year > self.current_year:
                return False, f"The claim references a future year ({year}), which is impossible."
            # We don't apply min_reasonable_year here to avoid false positives on numbers like "1500 people"
            
        return True, "No impossible dates detected."
