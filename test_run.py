import sys
import os
import json

print("Starting test")
try:
    from truth_mirror import TruthMirrorPipeline
    print("Import successful")
    
    pipeline = TruthMirrorPipeline()
    
    print("\n--- Test 1: Out of scope (Speed of light) ---")
    res1 = pipeline.verify("What is the speed of light")
    print(res1)
    
    print("\n--- Test 2: Out of scope (WW2) ---")
    res2 = pipeline.verify("World War 2 started in 1939")
    print(res2)
    
    print("\n--- Test 3: In scope ---")
    res3 = pipeline.verify("Iran nuclear deal was signed in 2026")
    print("Verdict:", getattr(res3, 'verdict', 'N/A') if hasattr(res3, 'verdict') else res3.get('verdict', 'N/A'))
    
except Exception as e:
    import traceback
    traceback.print_exc()

print("Test complete")
