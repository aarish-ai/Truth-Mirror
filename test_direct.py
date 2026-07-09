import logging
import sys
import os

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from truth_mirror.orchestrator import TruthMirrorPipeline

def main():
    pipeline = TruthMirrorPipeline()
    print("Testing pipeline directly...")
    result = pipeline.verify("US invaded venezuela")
    
    print("\n--- RESULTS ---")
    if hasattr(result, 'total_sources'):
        print(f"Total Sources: {result.total_sources}")
        print(f"Verdict: {result.verdict}")
        print(f"Hidden Stories: {len(getattr(result, 'hidden_stories', []))}")
    else:
        print("Result is not a GeopoliticalResult or is missing fields!")
        print(result)

if __name__ == "__main__":
    main()
