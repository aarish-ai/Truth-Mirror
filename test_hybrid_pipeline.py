import os
import json
import logging
from truth_mirror.local_decomposer import LocalDecomposer
from truth_mirror.kg_verifier import KGVerifier
from truth_mirror.gemini_analyzer import GeminiAnalyzer
from truth_mirror.orchestrator import TruthMirrorPipeline

logging.basicConfig(level=logging.WARNING)

def run_tests():
    print("--- Running Hybrid Pipeline Tests ---")
    
    # 2. DECOMPOSITION TEST
    try:
        decomposer = LocalDecomposer()
        claim = "Imran Khan is in jail as of June 2026"
        res = decomposer.decompose(claim)
        assert isinstance(res, list), "Result must be a list"
        assert len(res) >= 1, "List must have at least 1 element"
        assert len(res) <= 6, "List must have at most 6 elements"
        for item in res:
            assert isinstance(item, str) and item, "Each element must be a non-empty string"
        print("[PASS] Decomposition Test")
    except Exception as e:
        print(f"[FAIL] Decomposition Test: {e}")

    # 3. KG TEMPLATE TEST
    try:
        kg = KGVerifier()
        template, entity = kg._select_template("Who is the prime minister of Pakistan")
        assert template == "head_of_government", f"Expected head_of_government, got {template}"
        assert entity == "Pakistan", f"Expected Pakistan, got {entity}"
        print("[PASS] KG Template Test")
    except Exception as e:
        print(f"[FAIL] KG Template Test: {e}")

    # 4. PIPELINE INTEGRATION TEST & 1. BUDGET TEST
    try:
        GeminiAnalyzer.reset_call_count()
        orchestrator = TruthMirrorPipeline()
        result = orchestrator.verify("The Eiffel Tower is in Paris")
        assert result is not None
        assert result.final_verdict in ["Supported", "Partially supported", "Contradicted", "Unsupported", "Unclear"]
        print("[PASS] Pipeline Integration Test")
        
        # 1. BUDGET TEST
        assert GeminiAnalyzer._call_count == 1, f"Expected exactly 1 Gemini call, got {GeminiAnalyzer._call_count}"
        print("[PASS] Budget Test")
    except Exception as e:
        print(f"[FAIL] Pipeline & Budget Test: {e}")

if __name__ == "__main__":
    run_tests()
