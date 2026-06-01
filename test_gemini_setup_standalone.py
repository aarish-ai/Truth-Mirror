import asyncio
from truth_mirror.models import EvidenceItem
from truth_mirror.gemini_analyzer import GeminiAnalyzer

def test_gemini():
    analyzer = GeminiAnalyzer()
    print(f"Analyzer enabled: {analyzer.enabled}")
    if not analyzer.enabled:
        print("Failed to enable analyzer. Is API key set?")
        return

    evidence = [
        EvidenceItem(
            source_title="Example Title",
            source_type="journalism",
            publisher="Example Publisher",
            date="2020-11-04",
            url_or_id="http://example.com",
            excerpt="Biden won the 2020 election.",
            relevance_score=1.0,
            credibility_score=1.0
        )
    ]
    
    result = analyzer.synthesize("Biden won the Elections in 2020 in USA", evidence)
    print(f"Result: {result}")

if __name__ == '__main__':
    test_gemini()
