import json
from truth_mirror.orchestrator import TruthMirrorPipeline

def main():
    pipeline = TruthMirrorPipeline()
    
    claims = [
        "China has initiated a total blockade of Taiwan.",
        "The US has halted all weapon shipments to Israel.",
        "NATO forces have directly engaged Russian troops in Ukraine."
    ]
    
    for claim in claims:
        print(f"\n=============================================")
        print(f"VERIFYING: {claim}")
        print(f"=============================================")
        result = pipeline.verify(claim)
        
        # GeopoliticalResult returns source_analyses directly
        sources = getattr(result, "source_analyses", [])
        print(f"Total Sources Retrieved: {len(sources)}")
        for s in sources:
            print(f"  - [{s.get('alignment', 'Unknown')}] {s.get('source_name', 'Unknown')}")

if __name__ == "__main__":
    main()
