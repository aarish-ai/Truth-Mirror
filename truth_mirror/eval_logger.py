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

    def log_geo_run(self, geo_result: Any):
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write("=================================================================\n")
                f.write("--- GEOPOLITICAL INTELLIGENCE RUN ---\n")
                f.write(f"1. Original Claim:\n{getattr(geo_result, 'original_claim', 'Unknown')}\n\n")
                
                is_geo = getattr(geo_result, 'is_geopolitical', False)
                f.write(f"2. Is Geopolitical: {is_geo}\n")
                if not is_geo:
                    f.write(f"   Rejection Reason: {getattr(geo_result, 'rejection_reason', '')}\n")
                else:
                    f.write(f"3. Final Verdict: {getattr(geo_result, 'verdict', 'Unknown')} (Confidence: {getattr(geo_result, 'confidence', 0.0)})\n")
                    f.write(f"   Reasoning: {getattr(geo_result, 'verdict_reasoning', '')}\n")
                    f.write(f"   Source Agreement: {getattr(geo_result, 'source_agreement_level', '')}\n\n")
                    
                    story = getattr(geo_result, 'story', None)
                    if story:
                        f.write(f"4. Story Headline: {getattr(story, 'headline', 'Unknown')}\n")
                        f.write(f"   Background: {getattr(story, 'background', '')}\n")
                        f.write(f"   Current Situation: {getattr(story, 'current_situation', '')}\n\n")
                    else:
                        f.write(f"4. Story: None\n\n")
                    
                    has_dispute = getattr(geo_result, 'has_dispute', False)
                    f.write(f"5. Dispute Detected: {has_dispute}\n")
                    if has_dispute:
                        dispute_analysis = getattr(geo_result, 'dispute_analysis', None)
                        if dispute_analysis:
                            f.write(f"   Ground Truth (Conf: {getattr(dispute_analysis, 'ground_truth_confidence', 'Unknown')}): {getattr(dispute_analysis, 'most_likely_ground_truth', '')}\n")
                            f.write(f"   Reasoning: {getattr(dispute_analysis, 'ground_truth_reasoning', '')}\n")
                            f.write(f"   Contested Claims: {getattr(dispute_analysis, 'contested_claims', [])}\n")
                            narratives = getattr(dispute_analysis, 'narratives', [])
                            if narratives:
                                f.write("   Narratives:\n")
                                for n in narratives:
                                    f.write(f"     - [{getattr(n, 'bloc', 'Unknown')}] {getattr(n, 'claim', 'Unknown')}\n")
                            else:
                                f.write("   Narratives: None\n")
                            f.write("\n")
                f.write("=================================================================\n\n")
        except Exception as e:
            print(f"EvalLogger log_geo_run error: {e}")
