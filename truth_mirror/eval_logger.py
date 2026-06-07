import os
from typing import Any, List, Dict

class EvalLogger:
    def __init__(self):
        # eval.txt in the project root
        self.filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "eval.txt"))

    def log_run(
        self,
        original_query: str,
        decomposed_claims: List[str],
        context: Any,
        entities: List[str],
        sub_results: List[Any],
        gemini_result: Dict[str, Any],
        final_verdict: str
    ):
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write("=================================================================\n")
                f.write(f"1. Original Query:\n{original_query}\n\n")
                
                f.write(f"2. Decomposed Claims:\n")
                for claim in decomposed_claims:
                    f.write(f"  - {claim}\n")
                f.write("\n")
                
                f.write(f"3. Context & Entities:\n")
                f.write(f"  Entities: {entities}\n")
                f.write(f"  Context: {context}\n\n")
                
                f.write(f"4. Evidence retrieved per subclaim:\n")
                for sr in sub_results:
                    f.write(f"  Subclaim: {getattr(sr, 'subclaim', 'Unknown')}\n")
                    evidence = getattr(sr, 'evidence', [])
                    if not evidence:
                        f.write("    No evidence found.\n")
                    for e in evidence:
                        stance = getattr(e, 'stance', 'Unknown')
                        url = getattr(e, 'url_or_id', '')
                        text = getattr(e, 'text', '')
                        if len(text) > 100:
                            text = text[:100] + "..."
                        f.write(f"    - [{stance}] {url}: {text}\n")
                    f.write("\n")
                
                f.write(f"5. Final Gemini Synthesis and Verdict:\n")
                f.write(f"  Verdict: {final_verdict}\n")
                if gemini_result:
                    f.write(f"  Synthesis: {gemini_result.get('reasoning', '')}\n")
                else:
                    f.write("  Synthesis: None (Gemini Synthesis did not return a result)\n")
                f.write("=================================================================\n\n")
        except Exception as e:
            print(f"EvalLogger error: {e}")
