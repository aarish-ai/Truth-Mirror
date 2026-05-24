"""
Test the enhanced Truth Mirror with temporal validation and Gemini.
"""

from truth_mirror.orchestrator import TruthMirrorPipeline

def test_enhancements():
    """Test critical fixes."""
    
    pipeline = TruthMirrorPipeline()
    
    test_claims = [
        # Should be SUPPORTED (true, recent historical event)
        "Biden won the Elections in 2020 in USA",
        
        # Should be CONTRADICTED (temporally impossible)
        "Biden won the Elections in 756 in USA",
        
        # Should be CONTRADICTED (false claim)
        "Trump won the 2020 election",
        
        # Should be SUPPORTED (well-documented historical fact)
        "The moon landing happened in 1969",
        
        # Should be CONTRADICTED (obviously false)
        "The Earth is flat",
        
        # Should be SUPPORTED (recent verifiable fact)
        "COVID-19 pandemic started in 2019",
        
        # Should be CONTRADICTED (temporally impossible)
        "COVID-19 pandemic started in 1850",
        
        # Should be CONTRADICTED (future date)
        "Biden will win the 2050 election",
    ]
    
    print("="*70)
    print("TRUTH MIRROR ENHANCEMENT TESTS")
    print("="*70)
    
    for claim in test_claims:
        print(f"\nCLAIM: {claim}")
        print("-"*70)
        
        result = pipeline.verify(claim)
        
        print(f"VERDICT: {result.final_verdict}")
        print(f"CONFIDENCE: {result.confidence:.2f}")
        
        # Note: Depending on if Gemini synthesized it or heuristic fallback, the reasoning might be in different places.
        reasoning = "N/A"
        if hasattr(result, 'reasoning') and result.reasoning:
            reasoning = result.reasoning
        elif result.provenance:
            reasoning = result.provenance[-1]
            
        print(f"REASONING: {reasoning}")
        print("="*70)

if __name__ == '__main__':
    test_enhancements()
