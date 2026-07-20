import os
import json
import re
import logging
import requests
import time
from dotenv import load_dotenv
from typing import List, Optional
from truth_mirror.temporal_classifier import TemporalContext
from truth_mirror.groq_router import GROQ_SIMPLE_MODEL, GROQ_SIMPLE_FALLBACK, get_model_label, call_groq_with_key_rotation
from truth_mirror.run_tracker import tracker

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

logger = logging.getLogger(__name__)

class GeoQueryGenerator:
    """
    Generates targeted queries (News, Official, Regional) for geopolitical claims.
    As per architecture specifications, it attempts to use Groq to generate
    exactly 3 search queries per sub-claim. If Groq fails, it uses deterministic fallbacks.
    """
    def __init__(self, timeout: int = 120):
        from datetime import datetime
        self.current_date_str = datetime.now().strftime("%d %B %Y")
        self.timeout = timeout

    def generate(self, sub_claim: str, involved_parties: list[str], claim_subtype: str, temporal_context=None) -> list[str]:
        if sub_claim.lower().startswith("the period in question") or sub_claim.lower().startswith("the action is currently"):
            return []
        """
        Uses Groq to generate exactly 3 search queries:
        1. News query
        2. Official query
        3. Regional query
        Returns a list of 3 strings.
        """
        parties_str = ", ".join(involved_parties) if involved_parties else "Unknown"
        
        from datetime import datetime

        if temporal_context is not None and hasattr(temporal_context, 'needs_date'):
            if temporal_context.needs_date and temporal_context.date_qualifier:
                date_instruction = (
                    f"Today's date is {self.current_date_str}. "
                    f"This claim is about a {temporal_context.temporal_type.replace('_', ' ')}. "
                    f"Append '{temporal_context.date_qualifier}' to queries about current status. "
                    f"Do NOT restrict ALL queries to today — vary the temporal scope across queries.\n\n"
                )
            else:
                date_instruction = (
                    f"This claim is about a completed or specific past event. "
                    f"Do NOT append the current date to queries. "
                    f"Search for the event broadly across all time periods.\n\n"
                )
        else:
            # No temporal context provided — use safe default (append current date)
            date_instruction = (
                f"Today's date is {self.current_date_str}. "
                f"Add the current date to queries about ongoing or recent events.\n\n"
            )
        prompt = date_instruction + f"""You are a geopolitical intelligence search query generator.
Given a sub-claim, involved parties, and claim subtype, generate exactly 3 distinct search queries to retrieve maximum relevant information.
Return ONLY a JSON array of 3 strings. No markdown formatting, no explanations.

Generate: 1) international news query  2) official/government query
3) regional/local perspective query

Input Data:
Sub-claim: {sub_claim}
Involved Parties: {parties_str}
Claim Subtype: {claim_subtype}

Output JSON Array of 3 strings:
"""
        def _call_groq(prompt_str: str) -> list | None:
            payload = {
                "model": GROQ_SIMPLE_MODEL,
                "messages": [{"role": "user", "content": prompt_str}],
                "temperature": 0.1,
                "max_tokens": 256
            }

            content, status = call_groq_with_key_rotation(
                payload=payload,
                timeout=25,
                log_prefix="[GeoQueryGenerator]"
            )

            if status != "success" or content is None:
                record_status = "rate_limited" if status == "rate_limited" else "failed"
                tracker.record("query_generator", GROQ_SIMPLE_MODEL, "groq", record_status)

                # Try GROQ_SIMPLE_FALLBACK before giving up on Groq
                logger.info(f"[GeoQueryGenerator] Primary 8b failed. Trying fallback 8b "
                            f"({GROQ_SIMPLE_FALLBACK}).")
                fallback_payload = payload.copy()
                fallback_payload["model"] = GROQ_SIMPLE_FALLBACK

                content, status = call_groq_with_key_rotation(
                    payload=fallback_payload,
                    timeout=25,
                    log_prefix="[GeoQueryGenerator-fallback]"
                )

                if status != "success" or content is None:
                    tracker.record("query_generator", GROQ_SIMPLE_FALLBACK, "groq",
                                   "rate_limited" if status == "rate_limited" else "failed")
                    return None

                try:
                    parsed = json.loads(content)
                    tracker.record("query_generator", GROQ_SIMPLE_FALLBACK, "groq", "fallback_used")
                    if isinstance(parsed, list):
                        return parsed
                    for key in parsed:
                        if isinstance(parsed[key], list):
                            return parsed[key]
                    return None
                except Exception as e:
                    logger.warning(f"[GeoQueryGenerator] Fallback 8b parse failed: {e}")
                    tracker.record("query_generator", GROQ_SIMPLE_FALLBACK, "groq", "failed")
                    return None

            try:
                parsed = json.loads(content)
                logger.info("[GeoQueryGenerator] Groq call succeeded.")
                tracker.record("query_generator", GROQ_SIMPLE_MODEL, "groq", "success")
                if isinstance(parsed, list):
                    return parsed
                for key in parsed:
                    if isinstance(parsed[key], list):
                        return parsed[key]
                return None
            except Exception as e:
                logger.warning(f"[GeoQueryGenerator] Failed to parse Groq response: {e}")
                tracker.record("query_generator", GROQ_SIMPLE_MODEL, "groq", "failed")
                return None

        try:
            response_text = None
            openrouter_failed = False
            
            logger.info(f"[GeoQueryGenerator] Attempting Groq ({get_model_label(GROQ_SIMPLE_MODEL)}) for query generation.")
            groq_result = _call_groq(prompt)
            if groq_result is not None:
                response_text = json.dumps(groq_result)
            elif OPENROUTER_API_KEY:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://truthmirror.app",
                    "X-Title": "Truth Mirror"
                }
                payload = {
                    "model": "qwen/qwen3-next-80b-a3b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
                        if response.status_code == 429:
                            wait_time = (2 ** attempt) + 1
                            logger.warning(f"[GeoQueryGenerator] Rate limited on attempt {attempt+1}. Waiting {wait_time}s before retry.")
                            time.sleep(wait_time)
                            if attempt == max_retries - 1:
                                openrouter_failed = True
                            continue
                        response.raise_for_status()
                        response_text = response.json()["choices"][0]["message"]["content"]
                        openrouter_failed = False
                        tracker.record("query_generator", "qwen/qwen3-next-80b-a3b-instruct:free", "openrouter", "success")
                        break
                    except Exception as e:
                        logger.warning(f"OpenRouter failed ({e}).")
                        openrouter_failed = True
                        break
            if openrouter_failed:
                raise ValueError("OpenRouter API failed for query generation.")
            
            # Extract queries robustly
            queries = []
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if isinstance(v, list):
                            queries = v
                            break
                elif isinstance(parsed, list):
                    queries = parsed
            except Exception:
                start = response_text.find('[')
                end = response_text.rfind(']')
                if start != -1 and end != -1 and end > start:
                    try:
                        queries = json.loads(response_text[start:end+1])
                    except Exception:
                        pass
            
            # Ensure we always get exactly 3 queries
            if isinstance(queries, list) and len(queries) >= 3:
                return [str(q).strip() for q in queries[:3]]
            elif isinstance(queries, list) and len(queries) > 0:
                base = [str(q).strip() for q in queries]
                base.extend(self._get_fallback_queries(sub_claim, involved_parties))
                return base[:3]
            else:
                logger.warning("Groq returned invalid query format. Using fallback queries.")
                return self._get_fallback_queries(sub_claim, involved_parties)
                
        except Exception as e:
            logger.error(f"Groq query generation failed: {e}. Using deterministic fallbacks.")
            return self._get_fallback_queries(sub_claim, involved_parties)

    def _get_fallback_queries(self, sub_claim: str, involved_parties: list[str]) -> list[str]:
        """Deterministic fallback queries."""
        tracker.record("query_generator", "deterministic_fallback", "heuristic_fallback", "success")
        q1 = f"{sub_claim} Reuters AP News"
        q2 = f"{sub_claim} Al Jazeera TASS CGTN"
        q3 = f"{sub_claim} independent analysis"
        
        return [q1, q2, q3]
