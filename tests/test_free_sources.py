import pytest
from truth_mirror.models import EvidenceItem
from truth_mirror.credibility import CredibilityRegistry
import os

def test_source_types():
    registry_path = os.path.join(os.path.dirname(__file__), "..", "truth_mirror", "credibility_registry.json")
    registry = CredibilityRegistry.load(registry_path)
    
    # Test the 5 free source types
    source_types = ["official", "journalism", "academic", "database", "other"]
    
    expected_scores = {
        "official": 0.95,
        "database": 0.9,
        "academic": 0.87,
        "journalism": 0.78,
        "other": 0.55
    }
    
    for st in source_types:
        item = EvidenceItem(
            source_title="Test Title",
            source_type=st,
            publisher="Generic Publisher",
            date="2023-01-01",
            url_or_id="http://test.com",
            excerpt="Test excerpt"
        )
        score = registry.score(item)
        assert score == expected_scores[st]
