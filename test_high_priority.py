import unittest
from datetime import datetime, timezone
import dateutil.parser

from truth_mirror.temporal_validator import TemporalValidator
from truth_mirror.normalization import inject_temporal_context
from truth_mirror.search_planner import SearchPlanner
from truth_mirror.models import EvidenceItem

class TestHighPriorityFixes(unittest.TestCase):
    def test_temporal_validator(self):
        validator = TemporalValidator()
        
        # H9: Should NOT trigger on "2050 dollars"
        is_valid, _ = validator.validate("He spent 2050 dollars.")
        self.assertTrue(is_valid)

        # H9: Should trigger on "in 2050"
        is_valid, _ = validator.validate("The war will happen in 2050.")
        self.assertFalse(is_valid)

    def test_inject_temporal_context(self):
        # H19: Only inject when is_temporally_sensitive is True
        claim = "Water boils at 100 degrees"
        
        # Not sensitive
        res, has_date = inject_temporal_context(claim, is_temporally_sensitive=False)
        self.assertEqual(res, claim)
        self.assertFalse(has_date)
        
        # Sensitive
        res2, has_date2 = inject_temporal_context(claim, is_temporally_sensitive=True)
        self.assertIn("as of", res2)
        self.assertFalse(has_date2)
        
        # Already has date
        res3, has_date3 = inject_temporal_context("The 2024 election was held today.")
        self.assertTrue(has_date3)

    def test_deduplication(self):
        # H20: Deduplication for items without URL
        item1 = EvidenceItem(
            source_title="Generic Report",
            source_type="other",
            publisher="Test",
            date="2024-01-01",
            url_or_id="",
            excerpt="This is a test snippet."
        )
        item2 = EvidenceItem(
            source_title="Generic Report",
            source_type="other",
            publisher="Test",
            date="2024-01-01",
            url_or_id="",
            excerpt="This is a test snippet."
        )
        item3 = EvidenceItem(
            source_title="Different Report",
            source_type="other",
            publisher="Test",
            date="2024-01-01",
            url_or_id="",
            excerpt="A different snippet."
        )

        class MockRetriever:
            def retrieve(self, query, claim_type):
                return [item1, item2, item3]

        def mock_query_gen(q, *args):
            return [q]

        planner = SearchPlanner(MockRetriever(), mock_query_gen)
        results, _ = planner.retrieve_for_subclaim("test", "test", False)
        
        # Should be 2 items: item1/item2 are deduplicated, item3 is distinct
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].source_title, "Generic Report")
        self.assertEqual(results[1].source_title, "Different Report")

if __name__ == '__main__':
    unittest.main()
