import os
import json
import requests
import logging
from dataclasses import dataclass
from typing import Optional
from truth_mirror.groq_router import GROQ_SIMPLE_MODEL, GROQ_SIMPLE_FALLBACK, get_model_label, call_groq_with_key_rotation
from truth_mirror.run_tracker import tracker

logger = logging.getLogger(__name__)

@dataclass
class TemporalContext:
    temporal_type: str
    needs_date: bool
    date_qualifier: str
    reasoning: str

class TemporalClassifier:

    def __init__(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        self.current_month_year = now.strftime("%B %Y")
        self.current_year = str(now.year)

    def classify(self, claim: str) -> TemporalContext:
        """
        Classifies the temporal intent of a claim using Groq.
        Falls back to inject_temporal_context() if Groq fails.
        """
        prompt = f"""You are a temporal intent classifier for a geopolitical fact-checking system.
Today's date is {self.current_month_year}.

Your task: classify the temporal nature of a geopolitical claim to determine
whether search queries for this claim should include the current date.

CLAIM: "{claim}"

CLASSIFICATION RULES:

"current_state" — Claim describes an ONGOING situation, active conflict,
current relationship, or present-tense state of affairs. The answer changes
depending on when you ask. Needs current date in queries.
Examples: "X is bombing Y", "relations between A and B are deteriorating",
"X is under sanctions", "the war in Y is ongoing"

"recent_development" — Claim uses words like recently, latest, new, just,
or describes something that happened in the near past without specifying
when. Needs year-level date context but not today specifically.
Examples: "X recently signed a deal with Y", "the latest offensive by X",
"new missile tests by Y"

"historical_completed" — Claim describes a COMPLETED past event that is
not implied to have present-day continuation. Past tense, closed event.
No date needed — let search engines find all coverage freely.
Examples: "there was a war between X and Y", "X invaded Y", "X collapsed"

"specific_incident" — Claim describes a specific discrete incident the user
wants to look up. Could be recent or historical. Appending today's date
would prevent finding the actual event coverage.
Examples: "a missile struck X", "an airstrike hit Y", "X was assassinated"

RESPOND ONLY with this JSON object, no other text:
{{
  "temporal_type": "current_state|recent_development|historical_completed|specific_incident",
  "needs_date": true|false,
  "date_qualifier": "as of {self.current_month_year}" or "in {self.current_year}" or "",
  "reasoning": "one sentence explanation"
}}

Rules:
- needs_date is true ONLY for current_state and recent_development
- date_qualifier is empty string "" for historical_completed and specific_incident
- date_qualifier is "as of {self.current_month_year}" for current_state
- date_qualifier is "in {self.current_year}" for recent_development
- When in doubt between current_state and recent_development, choose current_state
- When in doubt between historical_completed and specific_incident, choose specific_incident
"""

        def _call_groq(prompt_str: str) -> dict | None:
            payload = {
                "model": GROQ_SIMPLE_MODEL,
                "messages": [{"role": "user", "content": prompt_str}],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "max_tokens": 200
            }

            content, status = call_groq_with_key_rotation(
                payload=payload,
                timeout=25,
                log_prefix="[TemporalClassifier]"
            )

            if status != "success" or content is None:
                record_status = "rate_limited" if status == "rate_limited" else "failed"
                tracker.record("temporal_classifier", GROQ_SIMPLE_MODEL, "groq", record_status)

                # Try GROQ_SIMPLE_FALLBACK before giving up on Groq
                logger.info(f"[TemporalClassifier] Primary 8b failed. Trying fallback 8b "
                            f"({GROQ_SIMPLE_FALLBACK}).")
                fallback_payload = payload.copy()
                fallback_payload["model"] = GROQ_SIMPLE_FALLBACK

                content, status = call_groq_with_key_rotation(
                    payload=fallback_payload,
                    timeout=25,
                    log_prefix="[TemporalClassifier-fallback]"
                )

                if status != "success" or content is None:
                    tracker.record("temporal_classifier", GROQ_SIMPLE_FALLBACK, "groq",
                                   "rate_limited" if status == "rate_limited" else "failed")
                    return None

                try:
                    parsed = json.loads(content)
                    tracker.record("temporal_classifier", GROQ_SIMPLE_FALLBACK, "groq", "fallback_used")
                    return parsed
                except Exception as e:
                    logger.warning(f"[TemporalClassifier] Fallback 8b parse failed: {e}")
                    tracker.record("temporal_classifier", GROQ_SIMPLE_FALLBACK, "groq", "failed")
                    return None

            try:
                parsed = json.loads(content)
                logger.info("[TemporalClassifier] Groq call succeeded.")
                tracker.record("temporal_classifier", GROQ_SIMPLE_MODEL, "groq", "success")
                return parsed
            except Exception as e:
                logger.warning(f"[TemporalClassifier] Failed to parse Groq response: {e}")
                tracker.record("temporal_classifier", GROQ_SIMPLE_MODEL, "groq", "failed")
                return None

        parsed = _call_groq(prompt)
        if parsed:
            return TemporalContext(
                temporal_type=parsed.get("temporal_type", "current_state"),
                needs_date=bool(parsed.get("needs_date", True)),
                date_qualifier=str(parsed.get("date_qualifier", "")),
                reasoning=str(parsed.get("reasoning", ""))
            )
        else:
            logger.warning("[TemporalClassifier] Groq call failed. Using fallback.")
            return self._fallback(claim)

    def _fallback(self, claim: str) -> TemporalContext:
        """
        Naive keyword-based fallback for when Groq is unavailable.
        Defaults to appending current date if uncertain.
        """
        from truth_mirror.normalization import inject_temporal_context

        _, has_date = inject_temporal_context(claim)

        if has_date:
            # Claim already has temporal markers — treat as recent_development
            tracker.record("temporal_classifier", "keyword_heuristic", "heuristic_fallback", "success")
            return TemporalContext(
                temporal_type="recent_development",
                needs_date=True,
                date_qualifier=f"in {self.current_year}",
                reasoning="Fallback: claim contains temporal marker"
            )
        else:
            # Default conservative: append current date
            tracker.record("temporal_classifier", "keyword_heuristic", "heuristic_fallback", "success")
            return TemporalContext(
                temporal_type="current_state",
                needs_date=True,
                date_qualifier=f"as of {self.current_month_year}",
                reasoning="Fallback: no temporal marker found, defaulting to current"
            )
