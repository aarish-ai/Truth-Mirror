import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

async def test():
    from truth_mirror.temporal_classifier import TemporalClassifier
    classifier = TemporalClassifier()
    res = classifier.classify("US invaded Iraq")
    print(f"Result 1: {res}")

    res2 = classifier.classify("US is actively conducting strikes on Iran")
    print(f"Result 2: {res2}")
    
    from truth_mirror.geo_orchestrator import GeopoliticalPipeline
    pipeline = GeopoliticalPipeline()
    try:
        from truth_mirror.claim_scope_gate import gate_claim
        gate_res = gate_claim("US invaded Iraq")
        print(f"Gate result: {gate_res}")
        final_res = await pipeline.run_async("US invaded Iraq", gate_res)
        if final_res:
            print(f"Pipeline Result verdict: {final_res.verdict_data}")
        else:
            print("Pipeline returned None")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
