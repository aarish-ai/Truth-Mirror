import os
import logging
from typing import Any, List, Dict

class EvalLogger:
    def __init__(self):
        # eval.txt in the project root
        self.filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "eval.txt"))
        self.logger = logging.getLogger("eval_logger")
        self.logger.setLevel(logging.INFO)
        
        # Only add handler if not already present
        if not self.logger.handlers:
            handler = logging.FileHandler(self.filepath, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
            self.logger.propagate = False

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
            lines = []
            lines.append("=================================================================")
            lines.append(f"1. Original Query:\n{original_query}\n")
            
            lines.append(f"2. Decomposed Claims:")
            for claim in decomposed_claims:
                lines.append(f"  - {claim}")
            lines.append("")
            
            lines.append(f"3. Context & Entities:")
            lines.append(f"  Entities: {entities}")
            lines.append(f"  Context: {context}\n")
            
            lines.append(f"4. Evidence retrieved per subclaim:")
            for sr in sub_results:
                lines.append(f"  Subclaim: {getattr(sr, 'subclaim', 'Unknown')}")
                evidence = getattr(sr, 'evidence', [])
                if not evidence:
                    lines.append("    No evidence found.")
                for e in evidence:
                    stance = getattr(e, 'stance', 'Unknown')
                    url = getattr(e, 'url_or_id', '')
                    text = getattr(e, 'text', '')
                    if len(text) > 100:
                        text = text[:100] + "..."
                    lines.append(f"    - [{stance}] {url}: {text}")
                lines.append("")
            
            lines.append(f"5. Final Gemini Synthesis and Verdict:")
            lines.append(f"  Verdict: {final_verdict}")
            if gemini_result:
                lines.append(f"  Synthesis: {gemini_result.get('reasoning', '')}")
            else:
                lines.append("  Synthesis: None (Gemini Synthesis did not return a result)")
            lines.append("=================================================================\n")
            
            self.logger.info("\n".join(lines))
        except Exception as e:
            logging.getLogger(__name__).error(f"EvalLogger error: {e}")

    def log_geo_run(self, geo_result: Any):
        try:
            lines = []
            lines.append("=================================================================")
            lines.append("--- GEOPOLITICAL INTELLIGENCE RUN ---")
            lines.append(f"1. Original Claim:\n{getattr(geo_result, 'original_claim', 'Unknown')}\n")
            
            is_geo = getattr(geo_result, 'is_geopolitical', False)
            lines.append(f"2. Is Geopolitical: {is_geo}")
            if not is_geo:
                lines.append(f"   Rejection Reason: {getattr(geo_result, 'rejection_reason', '')}")
            else:
                lines.append(f"3. Final Verdict: {getattr(geo_result, 'verdict', 'Unknown')} (Confidence: {getattr(geo_result, 'confidence', 0.0)})")
                lines.append(f"   Reasoning: {getattr(geo_result, 'verdict_reasoning', '')}")
                lines.append(f"   Source Agreement: {getattr(geo_result, 'source_agreement_level', '')}\n")
                
                story = getattr(geo_result, 'story', None)
                if story:
                    lines.append(f"4. Story Headline: {getattr(story, 'headline', 'Unknown')}")
                    lines.append(f"   Background: {getattr(story, 'background', '')}")
                    lines.append(f"   Current Situation: {getattr(story, 'current_situation', '')}\n")
                else:
                    lines.append(f"4. Story: None\n")
                
                has_dispute = getattr(geo_result, 'has_dispute', False)
                lines.append(f"5. Dispute Detected: {has_dispute}")
                if has_dispute:
                    dispute_analysis = getattr(geo_result, 'dispute_analysis', None)
                    if dispute_analysis:
                        lines.append(f"   Ground Truth (Conf: {getattr(dispute_analysis, 'ground_truth_confidence', 'Unknown')}): {getattr(dispute_analysis, 'most_likely_ground_truth', '')}")
                        lines.append(f"   Reasoning: {getattr(dispute_analysis, 'ground_truth_reasoning', '')}")
                        lines.append(f"   Contested Claims: {getattr(dispute_analysis, 'contested_claims', [])}")
                        narratives = getattr(dispute_analysis, 'narratives', [])
                        if narratives:
                            lines.append("   Narratives:")
                            for n in narratives:
                                lines.append(f"     - [{getattr(n, 'bloc', 'Unknown')}] {getattr(n, 'claim', 'Unknown')}")
                        else:
                            lines.append("   Narratives: None")
                        lines.append("")
            lines.append("=================================================================\n")
            
            self.logger.info("\n".join(lines))
        except Exception as e:
            logging.getLogger(__name__).error(f"EvalLogger log_geo_run error: {e}")
