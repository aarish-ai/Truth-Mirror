import json
from unittest.mock import patch
from truth_mirror import TruthMirrorPipeline

def run_tests():
    # Patch arxiv and requests to avoid hanging on network timeouts in the sandbox
    with patch('arxiv.Client.results', return_value=[]), patch('requests.get'), patch('requests.post', side_effect=TimeoutError("Mock timeout")):
        pipeline = TruthMirrorPipeline()
    
    geo_claim = "The US and Israel launched airstrikes on Iran in February 2026"
    non_geo_claim = "The iPhone 17 was released in 2025"
    
    print(f"Testing Non-Geo Claim: {non_geo_claim}")
    non_geo_res = pipeline.verify(non_geo_claim)
    
    print("\n--- Non-Geo Result ---")
    print(json.dumps(pipeline.to_json(non_geo_res), indent=2))
    
    print(f"\nTesting Geo Claim: {geo_claim}")
    geo_res = pipeline.verify(geo_claim)
    
    print("\n--- Geo Result ---")
    print(json.dumps(pipeline.to_json(geo_res), indent=2))
    
    assert type(geo_res).__name__ == "GeopoliticalResult"
    
    print("\nTests passed successfully!")

if __name__ == "__main__":
    run_tests()
