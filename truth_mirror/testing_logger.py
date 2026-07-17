import os
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any

from truth_mirror.models import GeopoliticalResult

class TestingLogger:
    def __init__(self):
        self.log_file = "testing.md"
        self.count_file = "testing_run_count.txt"
        self._lock = threading.Lock()

    def _get_and_increment_run_count(self) -> int:
        count = 1
        if os.path.exists(self.count_file):
            try:
                with open(self.count_file, "r") as f:
                    count = int(f.read().strip())
            except ValueError:
                pass
        
        with open(self.count_file, "w") as f:
            f.write(str(count + 1))
            
        return count

    def log_run(self, claim: str, result: GeopoliticalResult, model_events: List[Dict[str, Any]], elapsed_seconds: float):
        with self._lock:
            run_count = self._get_and_increment_run_count()
            utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            mins = int(elapsed_seconds // 60)
            secs = int(elapsed_seconds % 60)
            
            lines = []
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"RUN #{run_count}  |  {utc_now}")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            lines.append(f'CLAIM: "{claim}"')
            
            if not result.is_geopolitical:
                lines.append(f"RESULT: OUT OF SCOPE — {result.rejection_reason or 'Not geopolitical or out of timeframe'}")
                lines.append(f"RUNTIME: {mins}m {secs}s\n")
                lines.append("\n")
                
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                return
                
            lines.append(f"TOTAL RUNTIME: {mins}m {secs}s\n")
            
            lines.append("─── PIPELINE — MODELS USED ─────────────────────────────────")
            for event in model_events:
                stage = event.get("stage", "unknown")
                model = event.get("model", "unknown")
                provider = event.get("provider", "unknown")
                status = event.get("status", "unknown")
                # Add formatting arrow for rate_limited vs others? The instructions just say e.g. [rate_limited → ] but let's just stick to what's requested
                status_str = f"[{status}]"
                if status == "rate_limited":
                    status_str = "[rate_limited → ]"
                lines.append(f"{stage:<25} →  {model:<25} ({provider.capitalize()}) {status_str:>15}")
            lines.append("")
            
            lines.append("─── FINAL VERDICT ───────────────────────────────────────────")
            verdict = result.verdict or "N/A"
            confidence = result.confidence if result.confidence is not None else 0
            
            vd = result.verdict_data or {}
            
            label = vd.get("confidence_label") or "N/A"
            summary = vd.get("one_line_verdict") or "N/A"
            lines.append(f"Verdict:     {verdict}")
            lines.append(f"Confidence:  {confidence}%  ({label})")
            lines.append(f"Summary:     {summary}\n")
            
            lines.append("Full Reasoning:")
            lines.append(vd.get("full_reasoning") or "N/A")
            lines.append("")
            
            lines.append("Verified Facts:")
            lines.append(vd.get("what_is_true") or "N/A")
            lines.append("")
            
            lines.append("Disproven Elements:")
            lines.append(vd.get("what_is_false") or "N/A")
            lines.append("")
            
            lines.append("Unclear / Disputed:")
            lines.append(vd.get("what_is_unclear") or "N/A")
            lines.append("")
            
            lines.append(f"Strongest Evidence FOR:    {vd.get('strongest_evidence_for') or 'N/A'}")
            lines.append(f"Strongest Evidence AGAINST: {vd.get('strongest_evidence_against') or 'N/A'}")
            lines.append(f"Source Quality Note:       {vd.get('source_quality_note') or 'N/A'}")
            lines.append("")
            
            lines.append(f"─── SOURCES ANALYZED ({len(result.source_analyses)} total) ───────────────────────────")
            for idx, sa in enumerate(result.source_analyses, 1):
                name = sa.get("source_name") or "N/A"
                align = sa.get("alignment") or "N/A"
                tier = sa.get("reliability_tier") if sa.get("reliability_tier") is not None else "N/A"
                lines.append(f"[{idx}] {name}  ({align}, Tier {tier})")
                lines.append(f"    URL: {sa.get('url') or 'N/A'}")
                lines.append(f"    Stance: {sa.get('stance') or 'N/A'}  (Confidence: {(sa.get('stance_confidence') or 0) * 100}%)")
                lines.append(f"    Summary: {sa.get('summary') or 'N/A'}")
                key_claims = " | ".join(sa.get("key_claims") or []) if sa.get("key_claims") else "N/A"
                lines.append(f"    Key Claims: {key_claims}")
                lines.append(f"    Emphasizes: {sa.get('what_emphasized') or 'N/A'}")
                lines.append(f"    Omits: {sa.get('what_omitted') or 'N/A'}")
                if sa.get("hidden_implication"):
                    lines.append(f"    Hidden Implication: {sa.get('hidden_implication')}")
            lines.append("")
            
            lines.append("─── MEDIA BLOC PERSPECTIVES ─────────────────────────────────")
            for pg in result.perspective_groups:
                label = pg.get("group_label") or "N/A"
                lines.append(f"[{label}]  Collective Stance: {pg.get('collective_stance') or 'N/A'}")
                lines.append(f"  Narrative:    {pg.get('collective_narrative') or 'N/A'}")
                lines.append(f"  Emphasizes:   {pg.get('what_they_emphasize') or 'N/A'}")
                lines.append(f"  Omits:        {pg.get('what_they_omit') or 'N/A'}")
                if pg.get("internal_disagreements"):
                    lines.append(f"  Internal Disagreements: {pg.get('internal_disagreements')}")
                lines.append(f"  Credibility Note: {pg.get('credibility_note') or 'N/A'}")
            lines.append("")
            
            lines.append("─── HIDDEN STORIES ──────────────────────────────────────────")
            for idx, hs in enumerate(result.hidden_stories, 1):
                lines.append(f"Story {idx}: {hs.get('title') or 'N/A'}")
                lines.append(f"  Explanation:  {hs.get('explanation') or 'N/A'}")
                lines.append(f"  Significance: {hs.get('significance') or 'N/A'}")
                
                if hs.get("supporting_facts"):
                    facts = "\n  • ".join(hs.get("supporting_facts"))
                    lines.append(f"  Supporting Facts: \n  • {facts}")
                else:
                    lines.append("  Supporting Facts: N/A")
                    
                hinted = ", ".join(hs.get("which_sources_hint_at_this") or []) if hs.get("which_sources_hint_at_this") else "N/A"
                suppressed = ", ".join(hs.get("which_sources_suppress_this") or []) if hs.get("which_sources_suppress_this") else "N/A"
                lines.append(f"  Hinted at by:   {hinted}")
                lines.append(f"  Suppressed by:  {suppressed}")
            
            lines.append("\n")
            
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write("\n".join(lines))
