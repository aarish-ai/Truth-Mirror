import unittest
from unittest.mock import patch
from truth_mirror.query_generator import QueryGenerator
from datetime import datetime

class TestQueryGeneration(unittest.TestCase):
    def setUp(self):
        self.qg = QueryGenerator()
        
    @patch('truth_mirror.query_generator.requests.post')
    def test_ollama_failure_silent_fallback(self, mock_post):
        mock_post.side_effect = Exception("Ollama is down")
        
        queries = self.qg.generate_queries("Donald Trump is Dead", False)
        self.assertEqual(len(queries), 3)
        self.assertTrue(any("Donald Trump is Dead" in q for q in queries))
        
    @patch('truth_mirror.query_generator.QueryGenerator._call_ollama')
    def test_medical_guardrail(self, mock_call):
        # Mocks Ollama returning bad prefixes
        mock_call.return_value = '["Causes of Donald Trump death", "Symptoms of being dead", "What is death"]'
        
        queries = self.qg.generate_queries("Donald Trump is Dead", False)
        # Verify bad prefixes are replaced by fallbacks
        self.assertEqual(len(queries), 3)
        for q in queries:
            self.assertFalse(q.lower().startswith("causes of"))
            self.assertFalse(q.lower().startswith("symptoms of"))
            self.assertFalse(q.lower().startswith("what is"))

    @patch('truth_mirror.query_generator.QueryGenerator._call_ollama')
    def test_word_count_guardrail(self, mock_call):
        # Mocks Ollama returning a query that's too long
        long_query = "This is a very very very very very very very very very very very very very long query"
        mock_call.return_value = f'["{long_query}", "Short", "Donald Trump death status"]'
        
        queries = self.qg.generate_queries("Donald Trump is Dead", False)
        self.assertEqual(len(queries), 3)
        for q in queries:
            words = q.split()
            self.assertTrue(3 <= len(words) <= 15)

    @patch('truth_mirror.query_generator.QueryGenerator._call_ollama')
    def test_significant_word_guardrail(self, mock_call):
        # Mocks Ollama returning queries without the main entity
        # "Donald Trump is Dead" -> significant words: donald, trump, dead
        mock_call.return_value = '["Random unrelated query one", "Random unrelated query two", "Random unrelated query three"]'
        
        queries = self.qg.generate_queries("Donald Trump is Dead", False)
        self.assertEqual(len(queries), 3)
        # Should fallback to default queries which contain the claim itself
        self.assertTrue(any("Donald" in q for q in queries))
        self.assertTrue(any("Trump" in q for q in queries))
        
    def test_bare_claim_date_injection(self):
        # _fallback_queries directly uses current_date_str
        sub_claim = "Donald Trump is Dead"
        queries = self.qg._fallback_queries(sub_claim, has_date=False)
        self.assertTrue(any(self.qg.current_date_str in q for q in queries))
        
    def test_explicit_date_no_injection(self):
        sub_claim = "Donald Trump died in 2024"
        queries = self.qg._fallback_queries(sub_claim, has_date=True)
        # The exact implementation appends date only if has_date is False
        for q in queries:
            self.assertNotIn(self.qg.current_date_str, q)

if __name__ == "__main__":
    unittest.main()
