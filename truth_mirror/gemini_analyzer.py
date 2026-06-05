"""
Gemini API integration for intelligent evidence synthesis and verdict generation.
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any

try:
    from google import genai
    from google.genai import types
    from dotenv import load_dotenv
    DEPENDENCIES_MET = True
except ImportError:
    DEPENDENCIES_MET = False

from .models import EvidenceItem, VerdictLabel

logger = logging.getLogger(__name__)

class GeminiAnalyzer:
    """Synthesizes evidence using the Gemini API to produce a reasoned verdict."""

    def __init__(self):
        if not DEPENDENCIES_MET:
            logger.warning("google-genai or python-dotenv not installed. Gemini integration disabled.")
            self.enabled = False
            return
            
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            self.model_name = 'gemini-2.5-flash'
            self.enabled = True
        else:
            logger.warning("GEMINI_API_KEY not found. Gemini integration disabled.")
            self.enabled = False

    def synthesize(self, claim: str, evidence: List[EvidenceItem]) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini to analyze the evidence and return a structured verdict.
        Returns a dictionary with 'verdict', 'confidence', 'reasoning', 'evidence_summary'
        or None if disabled or API fails.
        """
        if not self.enabled:
            return None

        if not evidence:
            logger.info("No evidence provided for Gemini synthesis.")
            return None

        # Prepare evidence text safely without loading infinite text
        evidence_text = ""
        for i, ev in enumerate(evidence, 1):
            evidence_text += f"\n[Source {i}] {ev.source_title} ({ev.publisher}): {ev.excerpt}"

        prompt = f"""
You are an expert fact-checker. Please analyze the following claim against the provided evidence.

Claim: "{claim}"

Evidence:
{evidence_text}

Analyze the evidence and determine if the claim is Supported, Partially supported, Contradicted, Unsupported, or Unclear.

You must respond ONLY with a valid JSON object using the exact schema below. Do not include markdown formatting or extra text outside the JSON.

{{
  "verdict": "Supported" | "Partially supported" | "Contradicted" | "Unsupported" | "Unclear",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<A clear explanation of why you reached this verdict based on the evidence>",
  "evidence_summary": "<A short summary of what the evidence overall says>"
}}
"""
        try:
            # We use gemini-2.5-flash as it is free, fast, and supports JSON output natively
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    temperature=0.1
                )
            )
            result_json = response.text
            result = json.loads(result_json)
            
            # Validate the parsed result
            verdict = result.get("verdict")
            valid_verdicts = ["Supported", "Partially supported", "Contradicted", "Unsupported", "Unclear"]
            if verdict not in valid_verdicts:
                result["verdict"] = "Unclear"
                
            return {
                "verdict": result.get("verdict", "Unclear"),
                "confidence": float(result.get("confidence", 0.5)),
                "reasoning": result.get("reasoning", "Gemini analysis completed."),
                "evidence_summary": result.get("evidence_summary", "Synthesis generated.")
            }
            
        except Exception as e:
            logger.error(f"Gemini API failure: {e}")
            return None
