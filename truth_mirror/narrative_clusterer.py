"""
Narrative clustering module to detect geo-narrative divergence using an LLM.
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any

try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    DEPENDENCIES_MET = True
except ImportError:
    DEPENDENCIES_MET = False

from .models import EvidenceItem

logger = logging.getLogger(__name__)

class NarrativeClusterer:
    """Summarizes evidence clusters and detects geo-narrative divergence."""
    
    def __init__(self):
        if not DEPENDENCIES_MET:
            logger.warning("google-generativeai or python-dotenv not installed. Gemini integration disabled.")
            self.enabled = False
            return
            
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            self.enabled = True
        else:
            logger.warning("GEMINI_API_KEY not found. Gemini integration disabled.")
            self.enabled = False

    def cluster_and_detect_divergence(self, claim: str, evidence: List[EvidenceItem], registry: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini to summarize evidence clusters and detect geo-narrative divergence.
        """
        if not self.enabled:
            return None

        if not evidence:
            logger.info("No evidence provided for narrative clustering.")
            return None

        evidence_text = ""
        for i, ev in enumerate(evidence, 1):
            source_domain = ev.publisher
            region = "Unknown"
            if registry and source_domain in registry:
                region = registry[source_domain].get("regional_focus", "Unknown")
            evidence_text += f"\n[Source {i}] {ev.source_title} (Publisher: {ev.publisher}, Region: {region}): {ev.excerpt}"

        prompt = f"""
You are an expert geopolitical analyst. Please analyze the following claim against the provided evidence to detect how different regions or groups are framing the narrative.

Claim: "{claim}"

Evidence:
{evidence_text}

Task:
1. Summarize the main narrative clusters.
2. Detect if there is significant geo-narrative divergence (i.e., different regions presenting significantly different facts or framings).

You must respond ONLY with a valid JSON object using the exact schema below. Do not include markdown formatting or extra text outside the JSON.

{{
  "clusters": [
    {{
      "narrative": "<description of the narrative>",
      "regions_supporting": ["<region1>", "<region2>"]
    }}
  ],
  "divergence_detected": <true or false>,
  "divergence_summary": "<A short summary of the divergence if any>"
}}
"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            result = json.loads(response.text)
            
            return {
                "clusters": result.get("clusters", []),
                "divergence_detected": bool(result.get("divergence_detected", False)),
                "divergence_summary": result.get("divergence_summary", "")
            }
            
        except Exception as e:
            logger.error(f"Gemini API failure during clustering: {e}")
            return None
